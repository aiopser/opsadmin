import traceback

from rest_framework import serializers
from rest_framework.serializers import raise_errors_on_nested_writes
from rest_framework.utils import model_meta

from common.authmodel import AuthorModelMixin
from common.auth.request import get_user


class AuthorModelMixinModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuthorModelMixin
        fields = "__all__"


class StandardModelSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        request = validated_data.pop("request", False)
        raise_errors_on_nested_writes("create", self, validated_data)

        model_class = self.Meta.model
        info = model_meta.get_field_info(model_class)
        many_to_many = {}
        for field_name, relation_info in info.relations.items():
            if relation_info.to_many and field_name in validated_data:
                many_to_many[field_name] = validated_data.pop(field_name)

        try:
            if request:
                if hasattr(model_class, "created_by"):
                    validated_data["created_by"] = get_user(request)
                if hasattr(model_class, "updated_by"):
                    validated_data["updated_by"] = get_user(request)
            instance = model_class._default_manager.create(**validated_data)
        except TypeError:
            tb = traceback.format_exc()
            msg = (
                "Got a `TypeError` when calling `%s.%s.create()`. "
                "This may be because you have a writable field on the "
                "serializer class that is not a valid argument to "
                "`%s.%s.create()`. You may need to make the field "
                "read-only, or override the %s.create() method to handle "
                "this correctly.\nOriginal exception was:\n %s"
                % (
                    model_class.__name__,
                    model_class._default_manager.name,
                    model_class.__name__,
                    model_class._default_manager.name,
                    self.__class__.__name__,
                    tb,
                )
            )
            raise TypeError(msg)

        for field_name, value in many_to_many.items():
            getattr(instance, field_name).set(value)
        return instance

    def update(self, instance, validated_data):
        request = validated_data.pop("request", False)
        if request and hasattr(instance, "updated_by"):
            validated_data["updated_by"] = get_user(request)

        raise_errors_on_nested_writes("update", self, validated_data)
        info = model_meta.get_field_info(instance)
        m2m_fields = []
        for attr, value in validated_data.items():
            if attr in info.relations and info.relations[attr].to_many:
                m2m_fields.append((attr, value))
            else:
                setattr(instance, attr, value)

        instance.save()
        for attr, value in m2m_fields:
            getattr(instance, attr).set(value)
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["created_by"] = (
            instance.created_by.name
            if hasattr(instance, "created_by") and instance.created_by
            else None
        )
        representation["updated_by"] = (
            instance.updated_by.name
            if hasattr(instance, "updated_by") and instance.updated_by
            else None
        )
        return representation
