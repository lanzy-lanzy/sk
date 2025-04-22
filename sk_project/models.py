from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum
from decimal import Decimal

class User(AbstractUser):
    """
    User model to represent SK chairmen.
    """
    is_chairman = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to='profile_pics/', default='profile_pics/default_avatar.png', blank=True)
    address = models.TextField(blank=True, null=True)
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    is_approved = models.BooleanField(default=False, help_text='Designates whether this user has been approved by an admin.')
    groups = models.ManyToManyField(
        Group,
        verbose_name=_('groups'),
        blank=True,
        help_text=_(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name='sk_user_set',
        related_query_name='sk_user',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name='sk_user_set',
        related_query_name='sk_user',
    )

    def __str__(self):
        return self.get_full_name()

    def total_budget(self):
        return self.projects.aggregate(total=Sum('budget'))['total'] or 0

    def total_expenses(self):
        return self.projects.annotate(
            project_expenses=Sum('expenses__amount')
        ).aggregate(total=Sum('project_expenses'))['total'] or 0

class MainBudget(models.Model):
    year = models.PositiveIntegerField()
    total_budget = models.DecimalField(max_digits=10, decimal_places=2)
    chairman = models.ForeignKey(User, related_name='main_budgets', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Main Budgets"
        unique_together = ['year', 'chairman']

    def __str__(self):
        return f"Main Budget for {self.year} - Total: {self.total_budget} - Chairman: {self.chairman.username}"

    def calculate_usage_percentage(self):
        total_allocated = self.projects.aggregate(Sum('budget'))['budget__sum'] or 0
        if self.total_budget > 0:
            return (total_allocated / self.total_budget) * 100
        return 0

    @property
    def allocated_budget(self):
        return self.projects.aggregate(Sum('budget'))['budget__sum'] or 0

    @property
    def remaining_budget(self):
        return self.total_budget - self.allocated_budget

    @property
    def usage_percentage(self):
        if self.total_budget > 0:
            return (self.allocated_budget / self.total_budget) * 100
        return 0

class Project(models.Model):
    """
    Project model to represent individual projects funded from the main budget.
    """
    name = models.CharField(max_length=255)
    description = models.TextField()
    allocated_budget = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    main_budget = models.ForeignKey(MainBudget, related_name='projects', on_delete=models.SET_NULL, null=True)
    chairman = models.ForeignKey(User, related_name='projects', on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    STATUS_CHOICES = [
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ongoing')
    image = models.ImageField(upload_to='project_images/%Y/%m/%d/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ['start_date']

    def __str__(self):
        return self.name

    def total_expenses(self):
        return self.expenses.aggregate(total=models.Sum('amount'))['total'] or 0

    @property
    def remaining_budget(self):
        total_expenses = self.expenses.aggregate(total=models.Sum('amount'))['total'] or 0
        return self.budget - total_expenses

    @property
    def latest_image(self):
        latest_report = self.accomplishment_reports.order_by('-report_date').first()
        if latest_report:
            latest_image = latest_report.report_images.first()
            if latest_image:
                return latest_image.image
        return None

class Expense(models.Model):
    """
    Expense model to track expenditures related to projects.
    """
    project = models.ForeignKey(Project, related_name='expenses', on_delete=models.CASCADE)
    item_name = models.CharField(max_length=255)
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity = models.PositiveIntegerField(default=1)
    description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_incurred = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.item_name} - {self.amount} for {self.project.name}"

    class Meta:
        ordering = ['date_incurred']

class AccomplishmentReport(models.Model):
    """
    Accomplishment report model to represent project achievements.
    """
    project = models.ForeignKey(Project, related_name='accomplishment_reports', on_delete=models.CASCADE)
    report_date = models.DateField()
    report_details = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Report for {self.project.name} - {self.report_date}"

    class Meta:
        ordering = ['report_date']

class AccomplishmentReportImage(models.Model):
    """
    Model to store multiple images for accomplishment reports.
    """
    report = models.ForeignKey(AccomplishmentReport, related_name='report_images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='accomplishment_reports/%Y/%m/%d/')
    caption = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.report} - {self.created_at}"

    class Meta:
        ordering = ['created_at']

class Profile(models.Model):
    """
    Profile model for additional user information.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', default='profile_pics/default_avatar.png', blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    class Meta:
        verbose_name_plural = "Profiles"