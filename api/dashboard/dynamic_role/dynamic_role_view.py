from rest_framework.views import APIView
from db.user import Role, DynamicRole
from utils.permission import CustomizePermission, JWTUtils, role_required
from utils.response import CustomResponse
from .dynamic_role_serializer import DynamicRoleCreateSerializer, DynamicRoleListSerializer
from utils.utils import DateTimeUtils

class DynamicRoleAPI(APIView):
    authentication_classes = [CustomizePermission]

    def post(self, request): # create
        type = request.data['type']
        role = Role.objects.filter(title=request.data['role']).first()
        if role:
            role = role.id
        else:
            return CustomResponse(general_message='Role does not exist').get_failure_response()
        data = {'type': type, 'role': role}
        serializer = DynamicRoleCreateSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return CustomResponse(general_message='Dynamic Role created successfully', response=serializer.data).get_success_response()
        return CustomResponse(message=serializer.errors).get_failure_response()

    def get(self, request): # list
        dynamic_roles = DynamicRole.objects.values('type').distinct()
        data = [{'type': role['type']} for role in dynamic_roles]

        serializer = DynamicRoleListSerializer(data, many=True)
        return CustomResponse(response=serializer.data).get_success_response()

    def delete(self, request): # delete
        type = request.data['type']
        role = request.data['role']
        if dynamic_role := DynamicRole.objects.filter(type=type, role__title=role).first():
            dynamic_role.delete()
            return CustomResponse(
                general_message=f'Dynamic Role of type {type} and role {role} deleted successfully'
                ).get_success_response()
        return CustomResponse(
            general_message=f'No such Dynamic Role of type {type} and role {role} present'
            ).get_failure_response()

    def patch(self, request):
        user_id = JWTUtils.fetch_user_id(request)
        type = request.data['type']
        role = request.data['role']
        new_role = request.data['new_role']
        if dynamic_role := DynamicRole.objects.filter(type=type, role__title=role).first():
            new_role = Role.objects.filter(title=new_role).first()
            if new_role:
                new_role = new_role.id
            else:
                return CustomResponse(general_message='Role does not exist').get_failure_response()
            dynamic_role.role_id = new_role
            dynamic_role.updated_by_id = user_id
            dynamic_role.updated_at = DateTimeUtils.get_current_utc_time()
            dynamic_role.save()
            serializer = DynamicRoleListSerializer({'type':type})
            return CustomResponse(
                general_message=f'Dynamic Role of type {type} and role {role} updated successfully',
                response=serializer.data,
                ).get_success_response()
        return CustomResponse(
            general_message=f'No such Dynamic Role of type {type} and role {role} present'
            ).get_failure_response()