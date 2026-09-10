from django.urls import path

from reports import social_views, internal_views, proxy_views, app_release_views

urlpatterns = [
    path('internal/report-summary/upsert/', internal_views.upsert_daily_report_summary,
         name='upsert_daily_report_summary'),
    path('internal/fcm-devices/active/', internal_views.list_active_fcm_devices, name='list_active_fcm_devices'),

    path('api/app-version/', app_release_views.app_version, name='app_version'),

    path('api/get-reports/', proxy_views.proxy_get_reports, name='proxy_get_reports'),
    path('api/generate_pdf_report/', proxy_views.proxy_generate_pdf_report, name='proxy_generate_pdf_report'),

    path('api/register-fcm-token/', social_views.register_fcm_token, name='register_fcm_token'),
    path('api/get-report-reaction-status/', social_views.get_report_reaction_status, name='get_report_reaction_status'),
    path("api/post-report-reaction/", social_views.post_report_reaction, name="post_report_reaction"),
    path("api/post-comment/", social_views.post_comment, name="post_comment"),
    path("api/get-comments/", social_views.get_comments, name="get_comments"),
    path("api/delete-comment/", social_views.delete_comment, name="delete_comment"),
    path("api/post-comment-reaction/", social_views.post_comment_reaction, name="post_comment_reaction"),
    path('api/report-reaction-users/', social_views.get_report_reaction_users, name='get_report_reaction_users'),
    path('api/comment-reaction-users/', social_views.get_comment_reaction_users, name='get_comment_reaction_users'),
    path('api/update-comment/', social_views.update_comment, name='update_comment'),
]
