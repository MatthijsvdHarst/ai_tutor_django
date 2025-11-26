from __future__ import annotations

from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import ChatSession, Role, User


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name")

    def save(self, commit: bool = True):
        user = super().save(commit=commit)
        if commit:
            role, _ = Role.objects.get_or_create(name=Role.RoleEnum.STUDENT)
            user.roles.add(role)
        return user


class ChatMessageForm(forms.Form):
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=True)
    model_override = forms.ChoiceField(
        required=False,
        choices=(
            ("", "Default"),
            ("gpt-4o", "GPT-4o"),
            ("gpt-4o-mini", "GPT-4o mini"),
        ),
    )

    def clean_model_override(self):
        value = self.cleaned_data["model_override"]
        return value or None


class ProfileChatMessageForm(forms.Form):
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=True)
