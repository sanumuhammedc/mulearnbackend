from rest_framework.views import APIView

from db.task import VoucherLog, TaskList
from db.user import User
from utils.permission import CustomizePermission, JWTUtils, role_required
from utils.response import CustomResponse
from utils.utils import ImportCSV, CommonUtils
from utils.karma_voucher import generate_karma_voucher, generate_ordered_id
from .karma_voucher_serializer import VoucherLogCSVSerializer, VoucherLogSerializer
from utils.types import RoleType

import decouple
from email.mime.image import MIMEImage
from django.core.mail import EmailMessage

import uuid
from utils.utils import DateTimeUtils


class ImportVoucherLogAPI(APIView):
    authentication_classes = [CustomizePermission]

    @role_required([RoleType.ADMIN.value])
    def post(self, request):
        try:
            file_obj = request.FILES['voucher_log']
        except KeyError:
            return CustomResponse(general_message={'File not found.'}).get_failure_response()
        
        excel_data = ImportCSV()
        excel_data = excel_data.read_excel_file(file_obj)
        if not excel_data:
            return CustomResponse(general_message={'Empty csv file.'}).get_failure_response()

        temp_headers = ['karma', 'mail', 'task', 'month', 'week']
        first_entry = excel_data[0]
        for key in temp_headers:
            if key not in first_entry:
                return CustomResponse(general_message={f'{key} does not exist in the file.'}).get_failure_response()
            
        current_user = JWTUtils.fetch_user_id(request)
        
        valid_rows = []
        error_rows = []
        
        users_to_fetch = set()
        tasks_to_fetch = set()

        for row in excel_data[1:]:
            task_hashtag = row.get('task')
            mail = row.get('mail')
            
            users_to_fetch.add(mail)
            tasks_to_fetch.add(task_hashtag)

        # Fetch users and tasks in bulk
        users = User.objects.filter(email__in=users_to_fetch).values('id', 'email', 'first_name', 'last_name')
        tasks = TaskList.objects.filter(hashtag__in=tasks_to_fetch).values('id', 'hashtag')

        for user in users:
            user_dict = {user['email']: (
                user['id'],
                user['first_name'] if user['last_name'] is None else f"{user['first_name']} {user['last_name']}"
                )}
        task_dict = {task['hashtag']: task['id'] for task in tasks}

        count = 1
        for row in excel_data[1:]:
            task_hashtag = row.get('task')
            karma = row.get('karma')
            mail = row.get('mail')
            month = row.get('month')
            week = row.get('week')

            user_info = user_dict.get(mail)
            if user_info is None:
                row['error'] = f"Invalid email: {mail}"
                error_rows.append(row)
            else:
                user_id, full_name = user_info

                task_id = task_dict.get(task_hashtag)
                
                if task_id is None:
                    row['error'] = f"Invalid task hashtag: {task_hashtag}"
                    error_rows.append(row)
                elif karma == 0:
                    row['error'] = f"Karma cannot be 0"
                    error_rows.append(row)
                else:
                    # Prepare valid row data
                    row['user_id'] = user_id
                    row['task_id'] = task_id
                    row['id'] = str(uuid.uuid4())
                    row['code'] = generate_ordered_id(count)
                    row['claimed'] = False
                    row['created_by_id'] = current_user
                    row['updated_by_id'] = current_user
                    row['created_at'] = DateTimeUtils.get_current_utc_time()
                    row['updated_at'] = DateTimeUtils.get_current_utc_time()
                    count += 1
                    valid_rows.append(row)

                    # Prepare email context and attachment
                    from_mail = decouple.config("FROM_MAIL")
                    subject = "Congratulations on earning Karma points!"
                    text = """Greetings from GTech µLearn!

                    Great news! You are just one step away from claiming your internship/contribution Karma points. Simply post the Karma card attached to this email in the #task-dropbox channel and include the specified hashtag to redeem your points.
                    Name: {}
                    Email: {}""".format(full_name, mail)

                    month_week = month + '/' + week
                    karma_voucher_image = generate_karma_voucher(
                        name=str(full_name), karma=str(int(karma)), code=row["code"], hashtag=task_hashtag, month=month_week)
                    karma_voucher_image.seek(0)
                    email = EmailMessage(
                        subject=subject,
                        body=text,
                        from_email=from_mail,
                        to=[mail],
                    )
                    attachment = MIMEImage(karma_voucher_image.read())
                    attachment.add_header('Content-Disposition', 'attachment', filename=str(full_name) + '.jpg')
                    email.attach(attachment)
                    email.send(fail_silently=False)


        # Serialize and save valid voucher rows
        voucher_serializer = VoucherLogCSVSerializer(data=valid_rows, many=True)
        if voucher_serializer.is_valid():
            voucher_serializer.save()
        else:
            error_rows.append(voucher_serializer.errors)
                
        return CustomResponse(response={"Success": voucher_serializer.data, "Failed": error_rows}).get_success_response()


class VoucherLogAPI(APIView):
    authentication_classes = [CustomizePermission]

    @role_required([RoleType.ADMIN.value])
    def get(self, request): 
        voucher_queryset = VoucherLog.objects.all()
        paginated_queryset = CommonUtils.get_paginated_queryset(
            voucher_queryset, request,
            search_fields=["user__first_name", "user__last_name",
                           "task__title", "karma", "month", "week", "claimed",
                           "updated_by__first_name", "updated_by__last_name",
                           "created_by__first_name", "created_by__last_name"],
            sort_fields={'user':'user__first_name',
                            'code':'code',
                            'karma': 'karma',
                            'claimed':'claimed',
                            'task':'task__title',
                            'week':'week',
                            'month':'month',
                            'updated_by': 'updated_by',
                            'updated_at': 'updated_at',
                            'created_at': 'created_at'
                            }
        )
        voucher_serializer = VoucherLogSerializer(paginated_queryset.get('queryset'), many=True).data
        return CustomResponse().paginated_response(data=voucher_serializer,
                                                   pagination=paginated_queryset.get('pagination'))