from django.contrib import admin
from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


class UserCreationForm(forms.ModelForm):
    """cоздание админке (с паролем)"""
    password1 = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Подтверждение пароля', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name')

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Пароли не совпадают")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    #редактирования пользователя в админке
    password = ReadOnlyPasswordHashField(
        label="Пароль",
        help_text="Пароль хранится в зашифрованном виде. Чтобы изменить пароль, используйте форму смены пароля."
    )

    class Meta:
        model = User
        fields = (
            'email', 'password', 'first_name', 'last_name',
            'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'
        )

    def clean_password(self):
        # Возвращаем исходное значение, чтобы не перезаписывать хэш
        return self.initial.get("password")


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    add_form = UserCreationForm
    form = UserChangeForm
    model = User

    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'is_superuser')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Персональная информация', {'fields': ('first_name', 'last_name')}),
        ('Права доступа', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2', 'is_staff', 'is_active'),
        }),
    )
