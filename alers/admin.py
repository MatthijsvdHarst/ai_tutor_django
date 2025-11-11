from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from . import models


@admin.register(models.User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (("Roles", {"fields": ("roles",)}),)
    filter_horizontal = ("roles",)


admin.site.register(models.Role)
admin.site.register(models.Actor)
admin.site.register(models.Course)
admin.site.register(models.Prerequisite)
admin.site.register(models.LearningGoal)
admin.site.register(models.Specification)
admin.site.register(models.CourseInstructorProfile)
admin.site.register(models.Enrollment)
admin.site.register(models.ChatSession)
admin.site.register(models.Message)
admin.site.register(models.Profile)
admin.site.register(models.Checkpoint)
admin.site.register(models.Dashboard)
