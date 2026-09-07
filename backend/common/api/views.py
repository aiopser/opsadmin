from rest_framework.views import APIView


class StandardApiView(APIView):
    pass


class StandardOpenApiView(APIView):
    authentication_classes = []
    permission_classes = []
