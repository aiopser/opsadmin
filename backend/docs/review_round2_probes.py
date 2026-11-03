"""Read-only review diagnostics, using only isolated pytest resources."""
from datetime import timedelta
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate
from apps.jobs.test_schedule_one_off import actor, host, pool, version, make_schedule, fire, clocked_occurrence


@pytest.mark.django_db
def test_profile_permission_must_not_allow_superuser_escalation():
    from apps.permission.models import Permission, Role
    from apps.permission.services import sync_casbin_rules, CasbinEnforcerService
    from apps.user.views.user_profile import UserProfileViewSet

    user = get_user_model().objects.create_user(username='review-profile', password='Review123!', email='profile@example.test', phone='13800008801')
    role = Role.objects.create(name='Self profile only')
    role.permission.add(Permission.objects.create(code='review.profile.update', name='Own profile', type='api', path='/api/v1/users/profile', method='PUT'))
    user.role.add(role)
    sync_casbin_rules()
    CasbinEnforcerService.reload()
    request = APIRequestFactory().put('/api/v1/users/profile', {'is_superuser': True}, format='json')
    force_authenticate(request, user)
    response = UserProfileViewSet.as_view({'put': 'update_profile'})(request)
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.is_superuser is False


@pytest.mark.django_db
def test_clocked_expiry_equal_to_run_time_is_rejected(actor, host, pool, version):
    from apps.jobs.views import ScheduledJobViewSet

    run_at = timezone.now() + timedelta(hours=2)
    request = APIRequestFactory().post('/api/v1/jobs/scheduled-jobs', {'name':'impossible-window','workflow_version':version.pk,'worker_pool':pool.pk,'host_ids':[host.pk],'schedule_type':'once','run_at':run_at.isoformat(),'expires_at':run_at.isoformat()}, format='json')
    force_authenticate(request, actor)
    response = ScheduledJobViewSet.as_view({'post':'create'})(request)
    assert response.status_code == 400


@pytest.mark.django_db
def test_completed_once_cannot_be_reenabled_with_past_occurrence(actor, host, pool, version, monkeypatch):
    from apps.jobs.views import ScheduledJobViewSet

    monkeypatch.setattr('apps.jobs.tasks.enqueue_workflow_run', lambda run_id: None)
    schedule = make_schedule(version,pool,actor,host,schedule_type='once',run_at=timezone.now()-timedelta(minutes=1))
    assert fire(schedule,clocked_occurrence(schedule))['status']=='dispatched'
    request = APIRequestFactory().patch(f'/api/v1/jobs/scheduled-jobs/{schedule.pk}',{'enabled':True},format='json')
    force_authenticate(request,actor)
    response = ScheduledJobViewSet.as_view({'patch':'partial_update'})(request,pk=schedule.pk)
    assert response.status_code == 400


@pytest.mark.django_db
def test_new_windows_cloud_host_does_not_default_to_ssh():
    from apps.cmdb.models import AssetSource, AssetHost, AssetSyncRecord
    from apps.cmdb.tasks import sync_asset_source

    source=AssetSource.objects.create(code='review-win',name='Windows cloud',source_type='cloud')
    record=AssetSyncRecord.objects.create(source=source,payload=[{'source_id':'win-1','hostname':'windows','internal_ip':'10.0.0.91','os_family':'windows'}])
    sync_asset_source(record.pk)
    host=AssetHost.objects.get(source_id='win-1')
    assert host.connection_type=='winrm'
