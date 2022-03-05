from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response


class BaseViewSet(viewsets.ViewSet):
    def get_permissions(self):
        dangerous = ["create", "update", "partial_update", "destroy"]
        safe = ["list", "retrieve"]
        if self.action in safe:
            permission_classes = [AllowAny]
        elif self.action in dangerous:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = self.permission_classes
        return [permission() for permission in permission_classes]


class TestViewSet(BaseViewSet):
    @action(methods=["get"], detail=False, permission_classes=[AllowAny])
    @swagger_auto_schema(
        operation_summary="Get the courses of a specialization",
        responses={200: "Success", 404: "no pk was provided or an invalid pk was provided"}
    )
    def get_all(self, request):
        return Response(status=200,
                        data=["Hello", "Hi", "Hey"])
