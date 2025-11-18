from django.urls import path

from . import views

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("login/", views.UserLoginView.as_view(), name="login"),
    path("logout/", views.UserLogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("courses/", views.CourseListView.as_view(), name="courses"),
    path("courses/<int:pk>/enroll/", views.enroll, name="course-enroll"),
    path("courses/<int:pk>/chat/", views.chat_session, name="chat-session"),
    path("teacher/dashboards/", views.teacher_dashboard, name="teacher-dashboard"),
    path("admin/users/", views.admin_user_management, name="admin-user-management"),
    path("admin-tools/login-activity/", views.admin_login_activity, name="admin-login-activity"),
]