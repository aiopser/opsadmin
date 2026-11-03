from django.test import TestCase, override_settings
from cryptography.fernet import Fernet
from .serializers import JumpServerConnectionSerializer
from .client import signature_headers


@override_settings(CREDENTIAL_ENCRYPTION_KEY=Fernet.generate_key().decode())
class JumpServerTests(TestCase):
    def test_signature_binds_date(self):
        headers = signature_headers("key", "secret", "Tue, 27 Oct 2026 08:00:00 GMT")
        self.assertIn('Signature keyId="key"', headers["Authorization"])
        self.assertNotIn("secret", headers["Authorization"])

    def test_blank_secret_preserves_ciphertext(self):
        serializer = JumpServerConnectionSerializer(
            data={
                "name": "JMS",
                "endpoint": "https://jms.example.com",
                "key_id": "key",
                "secret": "secret",
                "node_id": "00000000-0000-0000-0000-000000000001",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        connection = serializer.save()
        encrypted = connection.secret_encrypted
        update = JumpServerConnectionSerializer(
            connection, data={"secret": ""}, partial=True
        )
        self.assertTrue(update.is_valid(), update.errors)
        self.assertEqual(update.save().secret_encrypted, encrypted)
        self.assertNotIn("secret_encrypted", serializer.data)


from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError
from apps.cmdb.models import AssetHost
from .models import JumpServerMapping
from .services import preview, confirm, execute
from .client import JumpServerClient, JumpServerError


@override_settings(CREDENTIAL_ENCRYPTION_KEY=Fernet.generate_key().decode())
class JumpServerWorkflowTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(
            username="jms-admin", password="test", is_superuser=True
        )
        serializer = JumpServerConnectionSerializer(
            data={
                "name": "JMS",
                "endpoint": "https://jms.example.com",
                "key_id": "key",
                "secret": "secret",
                "node_id": "00000000-0000-0000-0000-000000000001",
            }
        )
        serializer.is_valid(raise_exception=True)
        self.connection = serializer.save()
        self.host = AssetHost.objects.create(
            hostname="manual-host",
            internal_ip="10.1.1.1",
            os_family="linux",
            connection_type="ssh",
        )

    def test_preview_is_explicit_and_local(self):
        with patch.object(JumpServerClient, "request") as request:
            run = preview(self.connection, self.actor, [self.host.pk])
        request.assert_not_called()
        self.assertEqual(
            run.snapshot[0]["payload"]["protocols"], [{"name": "ssh", "port": 22}]
        )

    def test_host_change_invalidates_confirmation(self):
        run = preview(self.connection, self.actor, [self.host.pk])
        AssetHost.objects.filter(pk=self.host.pk).update(internal_ip="10.1.1.2")
        with self.assertRaises(ValidationError):
            confirm(run, self.actor)

    def test_mutex_rejects_second_confirmation(self):
        first = preview(self.connection, self.actor, [self.host.pk])
        second = preview(self.connection, self.actor, [self.host.pk])
        confirm(first, self.actor)
        with self.assertRaises(ValidationError):
            confirm(second, self.actor)

    def test_disabled_actor_fails_before_network(self):
        run = confirm(preview(self.connection, self.actor, [self.host.pk]), self.actor)
        self.actor.is_active = False
        self.actor.save()
        with patch.object(JumpServerClient, "request") as request:
            execute(run.pk)
        request.assert_not_called()
        run.refresh_from_db()
        self.assertEqual(run.status, "failed")

    def test_create_then_update_only_owned_uuid(self):
        run = confirm(preview(self.connection, self.actor, [self.host.pk]), self.actor)
        with patch.object(
            JumpServerClient,
            "request",
            side_effect=lambda method, path, payload=None: {"id": payload["id"]}
            if method == "POST"
            else {},
        ) as request:
            execute(run.pk)
        mapping = JumpServerMapping.objects.get(host=self.host)
        self.assertEqual(request.call_args_list[-1].args[0], "POST")
        self.assertEqual(
            request.call_args_list[-1].args[2]["id"], str(mapping.external_id)
        )
        run2 = confirm(preview(self.connection, self.actor, [self.host.pk]), self.actor)
        marker = f"CMDB:{self.connection.pk}:{self.host.pk}:{mapping.external_id}"
        with patch.object(
            JumpServerClient, "request", side_effect=[{}, {"comment": marker}, {}]
        ) as request:
            execute(run2.pk)
        self.assertEqual(
            [call.args[0] for call in request.call_args_list], ["GET", "GET", "PATCH"]
        )

    def test_foreign_marker_is_not_updated(self):
        import uuid

        JumpServerMapping.objects.create(
            connection=self.connection, host=self.host, external_id=uuid.uuid4()
        )
        run = confirm(preview(self.connection, self.actor, [self.host.pk]), self.actor)
        with patch.object(
            JumpServerClient, "request", side_effect=[{}, {"comment": "foreign"}]
        ) as request:
            execute(run.pk)
        self.assertEqual(request.call_count, 2)
        run.refresh_from_db()
        self.assertEqual(run.status, "failed")

    def test_metadata_and_redirect_are_blocked(self):
        serializer = JumpServerConnectionSerializer(
            self.connection, data={"endpoint": "http://169.254.169.254"}, partial=True
        )
        self.assertFalse(serializer.is_valid())
        response = MagicMock(status_code=302)
        with patch(
            "apps.integrations.client.socket.getaddrinfo",
            return_value=[(None, None, None, None, ("10.1.1.1", 443))],
        ), patch("apps.integrations.client.requests.Session") as session:
            session.return_value.__enter__.return_value.request.return_value = response
            with self.assertRaises(JumpServerError):
                JumpServerClient(self.connection).test()
            self.assertFalse(
                session.return_value.__enter__.return_value.request.call_args.kwargs[
                    "allow_redirects"
                ]
            )

    def test_missing_remote_retries_reserved_uuid(self):
        import uuid

        mapping = JumpServerMapping.objects.create(
            connection=self.connection, host=self.host, external_id=uuid.uuid4()
        )
        run = confirm(preview(self.connection, self.actor, [self.host.pk]), self.actor)
        with patch.object(
            JumpServerClient,
            "request",
            side_effect=[{}, None, {"id": str(mapping.external_id)}],
        ) as request:
            execute(run.pk)
        run.refresh_from_db()
        self.assertEqual(run.status, "succeeded")
        self.assertEqual(
            request.call_args_list[-1].args[2]["id"], str(mapping.external_id)
        )
