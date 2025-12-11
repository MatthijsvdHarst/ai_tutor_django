from django.urls import path

from . import views

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("login/", views.UserLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register, name="register"),
    path("profile/chat/", views.profile_chat, name="profile-chat"),
    path("profile/", views.profile_detail, name="profile-detail"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("courses/", views.CourseListView.as_view(), name="courses"),
    path("courses/<int:pk>/enroll/", views.enroll, name="course-enroll"),
    path("courses/<int:pk>/chat/", views.chat_session, name="chat-session"),
    path("courses/<int:pk>/chat/stream/", views.chat_session_stream, name="chat-session-stream"),
    path("teacher/dashboards/", views.teacher_dashboard, name="teacher-dashboard"),
    path("profile/chat/stream/", views.profile_chat_stream, name="profile-chat-stream"),
    path("admin/users/", views.admin_user_management, name="admin-user-management"),
    path("admin-tools/login-activity/", views.admin_login_activity, name="admin-login-activity"),
]
