from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user == obj.user


class IsShop(BasePermission):
    def has_permission(self, request, view):
        return request.user.type == 'shop'