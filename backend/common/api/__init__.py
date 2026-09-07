"""Lightweight package marker for common.api.

Keep this module free of eager imports so Django model loading does not
accidentally pull in serializers or auth-related models during app setup.
"""
