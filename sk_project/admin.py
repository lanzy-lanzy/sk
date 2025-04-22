from django.contrib import admin
from .models import User, MainBudget, Project, Expense, AccomplishmentReport, Profile
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Custom admin interface for the User model.
    """
    list_display = ('username', 'email', 'is_chairman', 'get_profile_picture', 'address', 'contact_number', 'is_approved', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'address', 'contact_number')
    list_filter = ('is_approved', 'is_chairman', 'is_staff', 'is_superuser', 'is_active', 'groups')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email', 'profile_picture', 'address', 'contact_number')}),
        ('Permissions', {'fields': ('is_approved', 'is_chairman', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )

    def get_profile_picture(self, obj):
        if obj.profile_picture:
            return format_html('<img src="{}" width="50" height="50" style="border-radius:50%;"/>', obj.profile_picture.url)
        return "-"
    get_profile_picture.short_description = 'Profile Picture'


@admin.register(MainBudget)
class MainBudgetAdmin(admin.ModelAdmin):
    """
    Admin interface for the MainBudget model.
    """
    list_display = ('year', 'total_budget', 'allocated_budget', 'remaining_budget', 'usage_percentage', 'chairman', 'created_at', 'updated_at')
    list_filter = ('year', 'chairman')
    search_fields = ('year', 'chairman__username', 'chairman__email')
    ordering = ('-year',)
    readonly_fields = ('allocated_budget', 'remaining_budget', 'usage_percentage', 'created_at', 'updated_at')

    def usage_percentage(self, obj):
        return f"{obj.calculate_usage_percentage():.2f}%"
    usage_percentage.short_description = 'Usage Percentage'


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """
    Admin interface for the Project model.
    """
    list_display = ('name', 'budget', 'allocated_budget', 'remaining_budget', 'main_budget', 'chairman', 'start_date', 'end_date', 'created_at', 'updated_at')
    list_filter = ('chairman', 'start_date', 'end_date')
    search_fields = ('name', 'description', 'chairman__username', 'main_budget__year')
    ordering = ('start_date',)
    readonly_fields = ('remaining_budget', 'created_at', 'updated_at')

    def remaining_budget(self, obj):
        return f"{obj.remaining_budget:.2f}"
    remaining_budget.short_description = 'Remaining Budget'


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    """
    Admin interface for the Expense model.
    """
    list_display = ('item_name', 'project', 'price_per_unit', 'quantity', 'amount', 'date_incurred', 'created_at', 'updated_at')
    list_filter = ('project', 'date_incurred')
    search_fields = ('item_name', 'project__name', 'description')
    ordering = ('-date_incurred',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AccomplishmentReport)
class AccomplishmentReportAdmin(admin.ModelAdmin):
    """
    Admin interface for the AccomplishmentReport model.
    """
    list_display = ('project', 'report_date', 'short_report_details', 'created_at', 'updated_at')
    list_filter = ('project', 'report_date')
    search_fields = ('project__name', 'report_details')
    ordering = ('-report_date',)
    readonly_fields = ('created_at', 'updated_at')

    def short_report_details(self, obj):
        return obj.report_details[:50] + "..." if len(obj.report_details) > 50 else obj.report_details
    short_report_details.short_description = 'Report Details'


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """
    Admin interface for the Profile model.
    """
    list_display = ('user', 'contact_number', 'address', 'get_profile_picture', 'updated_at')
    search_fields = ('user__username', 'contact_number', 'address')
    readonly_fields = ('updated_at',)

    def get_profile_picture(self, obj):
        if obj.profile_picture:
            return format_html('<img src="{}" width="50" height="50" style="border-radius:50%;"/>', obj.profile_picture.url)
        return "-"
    get_profile_picture.short_description = 'Profile Picture'
