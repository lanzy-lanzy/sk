from django.contrib.humanize.templatetags.humanize import intcomma
from django.db import models, transaction
from django.db.models import Q, Sum
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, Http404
from django.utils import timezone
from decimal import Decimal
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from datetime import datetime
import os
from django.conf import settings
from .models import MainBudget, Project, User, Expense, AccomplishmentReportImage, AccomplishmentReport, RegistrationCode
from .forms import (
    MainBudgetForm,
    ProjectForm,
    ExpenseForm,
    AccomplishmentReportForm,
    CustomUserCreationForm,
    UserProfileForm,
    AccomplishmentReportImageForm,
    CustomPasswordChangeForm,
    AdminUserEditForm
)
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

# User Authentication Views
def landing_page(request):
    # Get all completed projects first
    completed_projects = Project.objects.filter(
        status='completed'
    ).select_related('chairman').order_by('-end_date')

    projects_data = []
    for project in completed_projects:
        # Get the chairman's full address
        chairman = project.chairman
        address = chairman.address if chairman.address else "Address not available"

        # Get the latest accomplishment report image if project image is not available
        project_image = project.image
        if not project_image:
            project_image = project.latest_image

        project_info = {
            'title': project.name,
            'image': project_image,
            'chairman_name': chairman.get_full_name() or chairman.username,
            'chairman_logo': chairman.logo,  # Add the chairman's logo (barangay logo)
            'address': address,
            'completion_date': project.end_date,
            'description': project.description
        }
        projects_data.append(project_info)

    context = {
        'completed_projects': projects_data
    }
    return render(request, 'landing_page.html', context)

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                # Create user but don't save password yet
                user = form.save(commit=False)

                # Set additional fields
                user.first_name = form.cleaned_data.get('first_name')
                user.last_name = form.cleaned_data.get('last_name')
                user.date_of_birth = form.cleaned_data.get('date_of_birth')
                user.gender = form.cleaned_data.get('gender')
                user.contact_number = form.cleaned_data.get('contact_number')
                user.term_of_office = form.cleaned_data.get('term_of_office')
                user.address = form.cleaned_data.get('address')

                # Debug information
                print(f"Saving user with address: {user.address}")

                # Handle file uploads
                if 'profile_picture' in request.FILES:
                    user.profile_picture = request.FILES['profile_picture']

                if 'logo' in request.FILES:
                    user.logo = request.FILES['logo']

                # Save the user with the password
                user.save()

                # Mark the registration code as used
                code_value = form.cleaned_data.get('registration_code')
                try:
                    reg_code = RegistrationCode.objects.get(code=code_value)
                    reg_code.is_used = True
                    reg_code.used_by = user
                    reg_code.used_at = timezone.now()
                    reg_code.save()
                except RegistrationCode.DoesNotExist:
                    # This shouldn't happen due to form validation, but just in case
                    pass

                # Don't log in the user automatically - they need approval first
                messages.success(request, 'Your account has been created successfully! Please wait for admin approval before you can log in.')

                # Check if it's an AJAX request
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'redirect_url': reverse('login'),
                        'message': 'Your account has been created successfully! Please wait for admin approval before you can log in.'
                    })
                else:
                    return redirect('login')
        else:
            # If it's an AJAX request, return form errors as JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                errors = {}
                for field, error_list in form.errors.items():
                    errors[field] = [str(error) for error in error_list]
                return JsonResponse({
                    'success': False,
                    'errors': errors,
                    'error': 'Please correct the errors in the form.'
                })
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                # Check if the user is approved
                if user.is_approved or user.is_superuser:  # Superusers don't need approval
                    login(request, user)
                    redirect_url = 'admin_dashboard' if user.is_superuser else 'dashboard'
                    return JsonResponse({'success': True, 'redirect_url': reverse(redirect_url)})
                else:
                    return JsonResponse({
                        'success': False,
                        'error': 'Your account is pending approval. Please wait for an administrator to approve your account.',
                        'redirect_url': reverse('approval_pending')
                    })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid username or password.'
                })
        else:
            errors = dict(form.errors.items())
            return JsonResponse({
                'success': False,
                'error': 'Please correct the errors below.',
                'form_errors': errors
            })
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def approval_pending(request):
    return render(request, 'approval_pending.html')

def check_username_email(request):
    """Check if a username or email already exists in the database"""
    username = request.GET.get('username', None)
    email = request.GET.get('email', None)
    response_data = {'is_taken': False}

    if username:
        exists = User.objects.filter(username__iexact=username).exists()
        if exists:
            response_data['is_taken'] = True
            response_data['field'] = 'username'
            response_data['error_message'] = 'This username is already taken.'

    if email and not response_data['is_taken']:
        exists = User.objects.filter(email__iexact=email).exists()
        if exists:
            response_data['is_taken'] = True
            response_data['field'] = 'email'
            response_data['error_message'] = 'This email is already registered.'

    return JsonResponse(response_data)

def user_logout(request):
    logout(request)
    return redirect('landing_page')

@user_passes_test(lambda u: u.is_superuser)
def user_approval(request):
    # Get users pending approval
    pending_users = User.objects.filter(is_approved=False, is_superuser=False)
    # Get approved users
    approved_users = User.objects.filter(is_approved=True, is_superuser=False)

    context = {
        'pending_users': pending_users,
        'approved_users': approved_users
    }

    return render(request, 'user_approval.html', context)

@user_passes_test(lambda u: u.is_superuser)
def approve_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        user.is_approved = True
        user.save()
        messages.success(request, f'User {user.username} has been approved.')
    return redirect('user_approval')

@user_passes_test(lambda u: u.is_superuser)
def reject_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        user.delete()
        messages.success(request, f'User has been rejected and removed from the system.')
    return redirect('user_approval')

@user_passes_test(lambda u: u.is_superuser)
def view_user_details(request, user_id):
    user = get_object_or_404(User, id=user_id)
    form = AdminUserEditForm(instance=user)

    # Make all form fields read-only
    for field in form.fields.values():
        field.widget.attrs['readonly'] = True
        if hasattr(field.widget, 'can_add_related'):
            field.widget.can_add_related = False

    return render(request, 'edit_user.html', {
        'form': form,
        'user_being_edited': user,
        'view_only': True
    })

@user_passes_test(lambda u: u.is_superuser)
def edit_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        form = AdminUserEditForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, f'User {user.username} has been updated successfully.')
            return redirect('user_approval')
        else:
            messages.error(request, 'There was an error updating the user. Please check the form.')
    else:
        form = AdminUserEditForm(instance=user)

    return render(request, 'edit_user.html', {
        'form': form,
        'user_being_edited': user
    })

@user_passes_test(lambda u: u.is_superuser)
def generate_registration_code(request):
    """Generate a new registration code for user registration"""
    # Get active registration codes
    active_codes = RegistrationCode.objects.filter(
        Q(is_used=False) & (Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
    ).order_by('-created_at')

    if request.method == 'POST':
        expires_in_days = request.POST.get('expires_in_days')

        # Convert to integer if provided
        if expires_in_days:
            try:
                expires_in_days = int(expires_in_days)
            except ValueError:
                expires_in_days = None

        # Generate the code
        registration_code = RegistrationCode.generate_code(
            created_by=request.user,
            expires_in_days=expires_in_days
        )

        messages.success(request, f'New registration code generated: {registration_code.code}')

        # If it's an AJAX request, return the code as JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'code': registration_code.code,
                'expires_at': registration_code.expires_at.strftime('%Y-%m-%d %H:%M:%S') if registration_code.expires_at else None
            })

        # Redirect to the same page to show the new code in the list
        return redirect('generate_registration_code')

    context = {
        'active_codes': active_codes
    }

    return render(request, 'generate_registration_code.html', context)

# Dashboard and Budget Management Views

@login_required
def dashboard(request):
    main_budget = MainBudget.objects.filter(chairman=request.user).order_by('-year').first()
    if main_budget:
        remaining_budget = main_budget.remaining_budget
        usage_percentage = main_budget.usage_percentage
    else:
        remaining_budget = 0
        usage_percentage = 0
    projects = Project.objects.filter(chairman=request.user).annotate(
        total_expenses=models.Sum('expenses__amount')
    )

    total_expenses = sum(project.total_expenses or 0 for project in projects)
    active_projects_count = projects.count()
    ongoing_initiatives = projects.filter(end_date__gt=timezone.now()).count()
    projects_in_progress = projects.filter(start_date__lte=timezone.now(), end_date__gte=timezone.now()).count()
    cumulative_spending = total_expenses
    budget_utilization = (total_expenses / main_budget.total_budget * 100) if main_budget else 0

    for project in projects:
        project.budget_utilized = (project.total_expenses or 0) >= project.allocated_budget

    context = {
        'main_budget': main_budget,
        'remaining_budget': remaining_budget,
        'usage_percentage': usage_percentage,
        'projects': projects,
        'total_expenses': total_expenses,
        'active_projects_count': active_projects_count,
        'ongoing_initiatives': ongoing_initiatives,
        'projects_in_progress': projects_in_progress,
        'cumulative_spending': cumulative_spending,
        'budget_utilization': budget_utilization,
        # User information for sidebar
        'user_address': request.user.address,
        'user_contact_number': request.user.contact_number,
        'user_term_of_office': request.user.term_of_office,
    }
    return render(request, 'dashboard.html', context)

@login_required
def create_main_budget(request):
    from datetime import datetime
    current_year = datetime.now().year

    if request.method == 'POST':
        form = MainBudgetForm(request.POST)
        if form.is_valid():
            year = form.cleaned_data['year']
            # Server-side validation to ensure year is current or future
            if year < current_year:
                messages.error(request, f'Year must be {current_year} or later.')
                return render(request, 'create_main_budget.html', {'form': form, 'current_year': current_year})

            main_budget = form.save(commit=False)
            main_budget.chairman = request.user
            main_budget.save()
            messages.success(request, 'Main budget created successfully!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Error creating main budget. Please check your input.')
    else:
        form = MainBudgetForm(initial={'year': current_year})

    return render(request, 'create_main_budget.html', {'form': form, 'current_year': current_year})

@login_required
def create_new_year_budget(request):
    from datetime import datetime
    current_year = datetime.now().year

    if request.method == 'POST':
        form = MainBudgetForm(request.POST)
        if form.is_valid():
            year = form.cleaned_data['year']
            total_budget = form.cleaned_data['total_budget']

            # Server-side validation to ensure year is current or future
            if year < current_year:
                messages.error(request, f'Year must be {current_year} or later.')
                return redirect('dashboard')

            with transaction.atomic():
                # Get the previous year's budget
                previous_year_budget = MainBudget.objects.filter(
                    chairman=request.user,
                    year=year-1
                ).first()

                # Calculate remaining budget from previous year
                remaining_budget = 0
                if previous_year_budget:
                    remaining_budget = previous_year_budget.remaining_budget

                # Add remaining budget to the new total budget
                new_total_budget = total_budget + remaining_budget

                main_budget, created = MainBudget.objects.get_or_create(
                    chairman=request.user,
                    year=year,
                    defaults={'total_budget': new_total_budget}
                )

                if created:
                    messages.success(request, f'New budget for {year} created successfully! Total budget: ₱{new_total_budget:,.2f} (including ₱{remaining_budget:,.2f} from previous year)')
                else:
                    main_budget.total_budget = new_total_budget
                    main_budget.save()
                    messages.info(request, f'Budget for {year} updated successfully! Total budget: ₱{new_total_budget:,.2f} (including ₱{remaining_budget:,.2f} from previous year)')
        else:
            messages.error(request, 'Error creating new year budget. Please check your input.')
    return redirect('dashboard')

# Project Management Views

@login_required
def create_project(request):
    from datetime import datetime
    today = datetime.now().date()

    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES)
        if form.is_valid():
            # Server-side validation for dates
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']

            # Validate start date is today or in the future
            if start_date < today:
                messages.error(request, 'Start date must be today or a future date.')
                return redirect('dashboard')

            # Validate end date is after start date
            if end_date < start_date:
                messages.error(request, 'End date must be after the start date.')
                return redirect('dashboard')

            with transaction.atomic():
                project = form.save(commit=False)
                project.chairman = request.user
                project.allocated_budget = project.budget  # Set allocated_budget
                main_budget = MainBudget.objects.select_for_update().filter(chairman=request.user).latest('year')
                if main_budget.remaining_budget >= project.budget:
                    project.main_budget = main_budget
                    project.save()
                    messages.success(request, 'Project created successfully!')
                else:
                    messages.error(request, 'Insufficient funds in the main budget for this project.')
        else:
            # Get specific form errors
            error_messages = []
            for field, errors in form.errors.items():
                for error in errors:
                    error_messages.append(f"{field.capitalize()}: {error}")

            if error_messages:
                messages.error(request, f"Error creating project: {', '.join(error_messages)}")
            else:
                messages.error(request, 'Error creating project. Please check your input.')
    return redirect('dashboard')

@login_required
def project_detail(request, project_id):
    # For admin users, allow viewing any project
    # For chairmen, only allow viewing their own projects
    if request.user.is_superuser:
        project = get_object_or_404(Project, id=project_id)
    else:
        project = get_object_or_404(Project, id=project_id, chairman=request.user)

    expenses = project.expenses.all().order_by('-date_incurred')
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0
    remaining_budget = project.allocated_budget - total_expenses
    accomplishment_reports = project.accomplishment_reports.prefetch_related('report_images').all().order_by('-report_date')

    context = {
        'project': project,
        'expenses': expenses,
        'total_expenses': total_expenses,
        'remaining_budget': remaining_budget,
        'accomplishment_reports': accomplishment_reports,
    }
    return render(request, 'project_detail.html', context)

def all_projects(request):
    search_query = request.GET.get('search', '')
    projects = Project.objects.filter(chairman=request.user).annotate(
    total_expenses=models.Sum('expenses__amount')
)
    if search_query:
        projects = projects.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    context = {
        'projects': projects,
        'search_query': search_query,
    }
    return render(request, 'all_projects.html', context)

# Expense Management Views

@login_required
def add_expense(request, project_id):
    project = get_object_or_404(Project, id=project_id, chairman=request.user)
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.project = project
            expense.amount = expense.price_per_unit * expense.quantity
            total_expenses = project.expenses.aggregate(total=models.Sum('amount'))['total'] or 0
            remaining_budget = project.allocated_budget - total_expenses
            if expense.amount <= remaining_budget:
                expense.save()
                messages.success(request, 'Expense added successfully!')
            else:
                messages.error(request, 'Expense amount exceeds remaining budget!')
            return redirect('project_detail', project_id=project.id)
    else:
        form = ExpenseForm()
    return render(request, 'add_expense.html', {'form': form, 'project': project})

@login_required
def all_expenses(request):
    total_expenses = Project.objects.filter(chairman=request.user).aggregate(total=models.Sum('expenses__amount'))['total'] or 0
    projects = Project.objects.filter(chairman=request.user).annotate(
    total_expenses=models.Sum('expenses__amount')
    )

    search_query = request.GET.get('search', '')
    if search_query:
        projects = projects.filter(
            Q(name__icontains=search_query) |
            Q(expenses__item_name__icontains=search_query) |
            Q(expenses__description__icontains=search_query)
        ).distinct()

    context = {
        'projects': projects,
        'total_expenses': total_expenses,
        'search_query': search_query,
    }
    return render(request, 'all_expenses.html', context)

# Accomplishment Report Management Views

@login_required
def project_accomplishment_report(request, project_id):
    # For admin users, allow viewing any project's accomplishment reports
    # For chairmen, only allow viewing their own projects' accomplishment reports
    if request.user.is_superuser:
        project = get_object_or_404(Project, id=project_id)
    else:
        project = get_object_or_404(Project, id=project_id, chairman=request.user)

    accomplishment_reports = project.accomplishment_reports.all().order_by('-report_date')

    context = {
        'project': project,
        'accomplishment_reports': accomplishment_reports,
    }
    return render(request, 'project_accomplishment_report.html', context)

@login_required
def mark_project_completed(request, project_id):
    project = get_object_or_404(Project, id=project_id, chairman=request.user)

    if request.method == 'POST':
        # Check if there's at least one accomplishment report
        if project.accomplishment_reports.exists():
            project.status = 'completed'
            project.save()
            messages.success(request, f'Project "{project.name}" has been marked as completed and will now be displayed on the landing page.')
        else:
            messages.error(request, 'Please add at least one accomplishment report before marking the project as completed.')

    return redirect('project_accomplishment_report', project_id=project.id)

@login_required
def add_accomplishment_report(request, project_id):
    project = get_object_or_404(Project, id=project_id, chairman=request.user)

    if request.method == 'POST':
        form = AccomplishmentReportForm(request.POST)
        image_form = AccomplishmentReportImageForm(request.POST, request.FILES)

        if form.is_valid():
            with transaction.atomic():
                # Save the report first
                report = form.save(commit=False)
                report.project = project
                report.save()

                # Handle multiple image uploads
                if 'images' in request.FILES:
                    for image in request.FILES.getlist('images'):
                        AccomplishmentReportImage.objects.create(
                            report=report,
                            image=image
                        )

            messages.success(request, 'Accomplishment report added successfully.')
            return redirect('project_accomplishment_report', project_id=project.id)
    else:
        form = AccomplishmentReportForm()
        image_form = AccomplishmentReportImageForm()

    return render(request, 'add_accomplishment_report.html', {
        'form': form,
        'image_form': image_form,
        'project': project
    })

# Profile Management View

@login_required
def edit_profile(request):
    if request.method == 'POST':
        # Check which form was submitted
        if 'update_profile' in request.POST:
            # Profile update form was submitted
            profile_form = UserProfileForm(request.POST, request.FILES, instance=request.user)
            if profile_form.is_valid():
                user = profile_form.save(commit=False)

                # Handle additional fields for admin users
                if request.user.is_superuser:
                    if 'username' in profile_form.cleaned_data:
                        user.username = profile_form.cleaned_data['username']
                    if 'date_of_birth' in profile_form.cleaned_data:
                        user.date_of_birth = profile_form.cleaned_data['date_of_birth']
                    if 'gender' in profile_form.cleaned_data:
                        user.gender = profile_form.cleaned_data['gender']
                    if 'term_of_office' in profile_form.cleaned_data:
                        user.term_of_office = profile_form.cleaned_data['term_of_office']
                    if 'logo' in request.FILES:
                        user.logo = request.FILES['logo']

                user.save()
                messages.success(request, 'Your profile has been updated successfully!')
                return redirect('edit_profile')
            password_form = CustomPasswordChangeForm(user=request.user)
        elif 'change_password' in request.POST:
            # Password change form was submitted
            password_form = CustomPasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                password_form.save()  # This will hash the password automatically
                # Update the session to prevent the user from being logged out
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Your password has been changed successfully!')
                return redirect('edit_profile')
            profile_form = UserProfileForm(instance=request.user)
        else:
            # Default case
            profile_form = UserProfileForm(instance=request.user)
            password_form = CustomPasswordChangeForm(user=request.user)
    else:
        profile_form = UserProfileForm(instance=request.user)
        password_form = CustomPasswordChangeForm(user=request.user)

    return render(request, 'edit_profile.html', {
        'form': profile_form,
        'password_form': password_form,
        'is_admin': request.user.is_superuser
    })

# PDF Export Functionality

@login_required
def export_pdf_report(request):
    buffer = BytesIO()
    projects = Project.objects.filter(chairman=request.user)
    generate_pdf_report(buffer, request.user, projects)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="sk_budget_report.pdf"'
    return response

def generate_pdf_report(response, user, projects):
    doc = SimpleDocTemplate(response, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=28, textColor=colors.HexColor("#2C3E50"), spaceAfter=16, alignment=1)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=20, textColor=colors.HexColor("#34495E"), spaceBefore=16, spaceAfter=8)
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor("#2C3E50"), leading=14)
    subheading_style = ParagraphStyle('Subheading', parent=styles['Heading3'], fontSize=16, textColor=colors.HexColor("#16A085"), spaceBefore=12, spaceAfter=6)

    # Add Republic of the Philippines and Province of Zamboanga del Sur header
    header_text_style = ParagraphStyle(
        'HeaderText',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#2C3E50"),
        leading=14,
        spaceBefore=0,
        spaceAfter=0
    )

    elements.append(Paragraph("REPUBLIC OF THE PHILIPPINES", header_text_style))
    elements.append(Paragraph("PROVINCE OF ZAMBOANGA DEL SUR", header_text_style))
    elements.append(Paragraph("MUNICIPALITY OF DUMINGAG", header_text_style))

    # Add barangay information if available
    if user.address and 'Barangay' in user.address:
        # Extract barangay name from address
        try:
            barangay_name = user.address.split('Barangay')[1].strip().split(',')[0].strip()
            elements.append(Paragraph(f"BARANGAY {barangay_name.upper()}", header_text_style))
        except:
            # If we can't parse the address, just use the full address
            elements.append(Paragraph(f"BARANGAY", header_text_style))
    else:
        elements.append(Paragraph("BARANGAY", header_text_style))

    elements.append(Spacer(1, 0.1*inch))

    # Add logos to the header
    dumingag_logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'dumingag-logo-simple.jpg')

    # Create a table for the header with logos
    header_data = [[]]

    # Add Dumingag logo on the left
    if os.path.exists(dumingag_logo_path):
        try:
            # Try to load the image with PIL first to ensure it's valid
            from PIL import Image as PILImage
            pil_img = PILImage.open(dumingag_logo_path)

            # Convert to RGB if it's RGBA (transparent PNG)
            if pil_img.mode == 'RGBA':
                rgb_img = PILImage.new('RGB', pil_img.size, (255, 255, 255))
                rgb_img.paste(pil_img, mask=pil_img.split()[3])

                # Save to a temporary file
                import tempfile
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                rgb_img.save(temp_file.name, 'JPEG')
                temp_file.close()

                # Use the temporary file for ReportLab
                dumingag_logo = Image(temp_file.name)
            else:
                dumingag_logo = Image(dumingag_logo_path)

            dumingag_logo.drawWidth = 0.8*inch
            dumingag_logo.drawHeight = 0.8*inch
            header_data[0].append(dumingag_logo)
        except Exception as e:
            print(f"Error loading Dumingag logo: {str(e)}")
            header_data[0].append('')
    else:
        print(f"Dumingag logo not found at: {dumingag_logo_path}")
        header_data[0].append('')

    # Add title in the middle
    header_data[0].append(Paragraph("SK Budget Report", title_style))

    # Add barangay logo on the right (from user's logo)
    if user.logo and hasattr(user.logo, 'path') and os.path.exists(user.logo.path):
        barangay_logo = Image(user.logo.path)
        barangay_logo.drawWidth = 0.8*inch
        barangay_logo.drawHeight = 0.8*inch
        header_data[0].append(barangay_logo)
    else:
        header_data[0].append('')

    # Create the header table
    header_table = Table(header_data, colWidths=[1*inch, 5*inch, 1*inch])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(header_table)
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#3498DB"), spaceAfter=0.2*inch))

    # Chairman information
    elements.append(Paragraph("Chairman Information", heading_style))
    chairman_info = [
        [Paragraph(f"<b>Name:</b> {user.get_full_name()}", normal_style)],
        [Paragraph(f"<b>Email:</b> {user.email}", normal_style)],
        [Paragraph(f"<b>Contact:</b> {user.contact_number}", normal_style)],
        [Paragraph(f"<b>Address:</b> {user.address or 'Not provided'}", normal_style)]
    ]
    chairman_table = Table(chairman_info, colWidths=[6*inch])
    chairman_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#ECF0F1")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#BDC3C7")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(chairman_table)
    elements.append(Spacer(1, 0.3*inch))

    for project in projects:
        elements.append(Paragraph(f"Project: {project.name}", subheading_style))

        # Project summary
        project_data = [
            ["Budget", "Expenses", "Remaining"],
            [f"{project.budget:,.2f}", f"{project.total_expenses():,.2f}", f"{project.remaining_budget:,.2f}"]
        ]

        project_table = Table(project_data, colWidths=[2*inch, 2*inch, 2*inch])
        project_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#3498DB")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 12),
            ('BOTTOMPADDING', (0,0), (-1,0), 8),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#ECF0F1")),
            ('TEXTCOLOR', (0,1), (-1,-1), colors.HexColor("#2C3E50")),
            ('ALIGN', (0,1), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,1), (-1,-1), 11),
            ('TOPPADDING', (0,1), (-1,-1), 6),
            ('BOTTOMPADDING', (0,1), (-1,-1), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#BDC3C7"))
        ]))
        elements.append(project_table)
        elements.append(Spacer(1, 0.2*inch))

        # Expense details
        elements.append(Paragraph("Expense Details", subheading_style))
        expense_data = [["Item Name", "Description", "Quantity", "Price per Unit", "Amount"]]
        for expense in project.expenses.all():
            expense_data.append([
                expense.item_name,
                expense.description,
                str(expense.quantity),
                f"{expense.price_per_unit:,.2f}",
                f"{expense.amount:,.2f}"
            ])

        expense_table = Table(expense_data, colWidths=[1.5*inch, 2*inch, 1*inch, 1.25*inch, 1.25*inch])
        expense_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#16A085")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 11),
            ('BOTTOMPADDING', (0,0), (-1,0), 8),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#E8F6F3")),
            ('TEXTCOLOR', (0,1), (-1,-1), colors.HexColor("#2C3E50")),
            ('ALIGN', (0,1), (1,-1), 'LEFT'),
            ('ALIGN', (2,1), (-1,-1), 'RIGHT'),
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,1), (-1,-1), 10),
            ('TOPPADDING', (0,1), (-1,-1), 4),
            ('BOTTOMPADDING', (0,1), (-1,-1), 4),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#BDC3C7"))
        ]))
        elements.append(expense_table)
        elements.append(Spacer(1, 0.3*inch))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#BDC3C7"), spaceAfter=0.2*inch))

    # Add page numbers
    def add_page_number(canvas, doc):
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#7F8C8D"))
        canvas.drawRightString(7.5*inch, 0.25*inch, text)

    doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)

@login_required
def export_project_pdf(request, project_id):
    project = get_object_or_404(Project, id=project_id)

    # Create response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{project.name.replace(" ", "_")}_report.pdf"'

    # Create the PDF object using ReportLab with A4 size
    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=colors.HexColor('#1a5f7a'),
        spaceAfter=30,
        alignment=TA_CENTER,
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=colors.HexColor('#1a5f7a'),
        spaceAfter=20,
    )

    header_text_style = ParagraphStyle(
        'HeaderText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1a5f7a'),
        leading=14,
        spaceBefore=0,
        spaceAfter=0
    )

    elements = []

    # Add Republic of the Philippines, Province of Zamboanga del Sur, and Municipality of Dumingag header
    elements.append(Paragraph("REPUBLIC OF THE PHILIPPINES", header_text_style))
    elements.append(Paragraph("PROVINCE OF ZAMBOANGA DEL SUR", header_text_style))
    elements.append(Paragraph("MUNICIPALITY OF DUMINGAG", header_text_style))

    # Add barangay information if available
    if project.chairman.address and 'Barangay' in project.chairman.address:
        # Extract barangay name from address
        try:
            barangay_name = project.chairman.address.split('Barangay')[1].strip().split(',')[0].strip()
            elements.append(Paragraph(f"BARANGAY {barangay_name.upper()}", header_text_style))
        except:
            # If we can't parse the address, just use the full address
            elements.append(Paragraph(f"BARANGAY", header_text_style))
    else:
        elements.append(Paragraph("BARANGAY", header_text_style))

    elements.append(Spacer(1, 0.1*inch))

    # Add logos to the header
    dumingag_logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'dumingag-logo.png')

    # Create a table for the header with logos
    header_data = [[]]

    # Add Dumingag logo on the left
    if os.path.exists(dumingag_logo_path):
        try:
            # Try to load the image with PIL first to ensure it's valid
            from PIL import Image as PILImage
            pil_img = PILImage.open(dumingag_logo_path)

            # Convert to RGB if it's RGBA (transparent PNG)
            if pil_img.mode == 'RGBA':
                rgb_img = PILImage.new('RGB', pil_img.size, (255, 255, 255))
                rgb_img.paste(pil_img, mask=pil_img.split()[3])

                # Save to a temporary file
                import tempfile
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                rgb_img.save(temp_file.name, 'JPEG')
                temp_file.close()

                # Use the temporary file for ReportLab
                dumingag_logo = Image(temp_file.name)
            else:
                dumingag_logo = Image(dumingag_logo_path)

            dumingag_logo.drawWidth = 0.8*inch
            dumingag_logo.drawHeight = 0.8*inch
            header_data[0].append(dumingag_logo)
        except Exception as e:
            print(f"Error loading Dumingag logo: {str(e)}")
            header_data[0].append('')
    else:
        print(f"Dumingag logo not found at: {dumingag_logo_path}")
        header_data[0].append('')

    # Add title in the middle
    header_data[0].append(Paragraph(project.name, title_style))

    # Add barangay logo on the right (from chairman's logo)
    if project.chairman.logo and hasattr(project.chairman.logo, 'path') and os.path.exists(project.chairman.logo.path):
        barangay_logo = Image(project.chairman.logo.path)
        barangay_logo.drawWidth = 0.8*inch
        barangay_logo.drawHeight = 0.8*inch
        header_data[0].append(barangay_logo)
    else:
        header_data[0].append('')

    # Create the header table
    header_table = Table(header_data, colWidths=[1*inch, 5*inch, 1*inch])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(header_table)
    elements.append(HRFlowable(
        width="100%",
        thickness=2,
        color=colors.HexColor('#1a5f7a'),
        spaceBefore=10,
        spaceAfter=20
    ))

    # Project Overview
    elements.append(Paragraph("Project Overview", heading_style))
    overview_data = [
        ["Chairman", project.chairman.get_full_name()],
        ["Start Date", project.start_date.strftime('%B %d, %Y')],
        ["End Date", project.end_date.strftime('%B %d, %Y')],
        ["Status", project.get_status_display()],
        ["Description", project.description]
    ]

    overview_table = Table(overview_data, colWidths=[100, 400])
    overview_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e9ecef')),
        ('PADDING', (0, 0), (-1, -1), 8)
    ]))
    elements.append(overview_table)
    elements.append(Spacer(1, 20))

    # Budget Information
    elements.append(Paragraph("Budget Information", heading_style))
    budget_data = [
        ["Allocated Budget", f"PHP {project.allocated_budget:,.2f}"],
        ["Total Expenses", f"PHP {project.total_expenses():,.2f}"],
        ["Remaining Budget", f"PHP {project.remaining_budget:,.2f}"]
    ]

    budget_table = Table(budget_data, colWidths=[100, 400])
    budget_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e9ecef')),
        ('PADDING', (0, 0), (-1, -1), 8)
    ]))
    elements.append(budget_table)
    elements.append(Spacer(1, 20))

    # Expenses
    if project.expenses.exists():
        elements.append(Paragraph("Expense Details", heading_style))
        expense_data = [["Date", "Item", "Amount", "Description"]]
        for expense in project.expenses.all().order_by('-date_incurred'):
            expense_data.append([
                expense.date_incurred.strftime('%Y-%m-%d'),
                expense.item_name,
                f"PHP {expense.amount:,.2f}",
                expense.description
            ])

        expense_table = Table(expense_data, colWidths=[80, 100, 100, 220])
        expense_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5f7a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e9ecef')),
            ('PADDING', (0, 0), (-1, -1), 8)
        ]))
        elements.append(expense_table)
        elements.append(Spacer(1, 20))

    # Project Images
    accomplishment_reports = project.accomplishment_reports.all()
    if accomplishment_reports.exists():
        elements.append(Paragraph("Project Images", heading_style))

        for report in accomplishment_reports:
            if report.report_images.exists():
                elements.append(Paragraph(f"Report Date: {report.report_date.strftime('%B %d, %Y')}", normal_style))
                elements.append(Spacer(1, 10))

                for img in report.report_images.all():
                    try:
                        # Get the full path of the image
                        img_path = img.image.path
                        # Add image to PDF with 120x120 dimensions
                        img_obj = Image(img_path)
                        img_obj.drawWidth = 120
                        img_obj.drawHeight = 120
                        elements.append(img_obj)
                        elements.append(Spacer(1, 10))
                        if img.caption:
                            elements.append(Paragraph(f"Caption: {img.caption}", normal_style))
                            elements.append(Spacer(1, 20))
                    except Exception as e:
                        elements.append(Paragraph(f"Error loading image: {str(e)}", normal_style))
                        elements.append(Spacer(1, 10))

    # Add signature section
    elements.append(PageBreak())

    elements.append(Spacer(1, 1*inch))  # Space before signature

    # Report Date
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=11,
        alignment=TA_LEFT,
    )
    elements.append(Paragraph(f"Report Date: {timezone.now().strftime('%B %d, %Y')}", date_style))
    elements.append(Spacer(1, 2*inch))

    # Signature line and details
    signature_data = [
        [Paragraph("Certified Correct:", normal_style)],
        [Spacer(1, 1*inch)],  # Space for actual signature
        [HRFlowable(width=200, thickness=1, color=colors.black)],
        [Paragraph(f"<b>{project.chairman.get_full_name().upper()}</b>", normal_style)],
        [Paragraph("SK Chairman", normal_style)]
    ]

    signature_table = Table(signature_data, colWidths=[4*inch])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))

    # Center the signature table on A4 page
    signature_wrapper = Table([[signature_table]], colWidths=[A4[0]-72])  # 72 points = 1 inch margins
    signature_wrapper.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))

    elements.append(signature_wrapper)

    # Build PDF
    doc.build(elements)
    return response

def get_project_status(project):
    current_date = timezone.now().date()
    if project.end_date < current_date:
        return "Completed"
    elif project.start_date <= current_date <= project.end_date:
        return "In Progress"
    else:
        return "Not Started"

@login_required
def edit_expense(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id)
    project = expense.project

    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense updated successfully.')
            return redirect('project_detail', project_id=project.id)
    else:
        form = ExpenseForm(instance=expense)

    context = {
        'form': form,
        'expense': expense,
        'project': project,
        'is_edit': True
    }
    return render(request, 'add_expense.html', context)

@login_required
def delete_expense(request, expense_id):
    if request.method == 'POST':
        expense = get_object_or_404(Expense, id=expense_id)
        project_id = expense.project.id
        expense.delete()
        messages.success(request, 'Expense deleted successfully.')
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@login_required
def edit_project(request, project_id):
    project = get_object_or_404(Project, id=project_id, chairman=request.user)
    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, 'Project updated successfully!')
            return redirect('dashboard')
    else:
        form = ProjectForm(instance=project)
    return render(request, 'edit_project.html', {'form': form, 'project': project})

@login_required
def delete_project(request, project_id):
    project = get_object_or_404(Project, id=project_id, chairman=request.user)
    project.delete()
    messages.success(request, 'Project deleted successfully!')
    return redirect('dashboard')

from django.contrib.auth.decorators import user_passes_test

@user_passes_test(lambda u: u.is_superuser)
def admin_dashboard(request):
    # Get all search parameters
    search_query = request.GET.get('search', '')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    min_budget = request.GET.get('min_budget')
    max_budget = request.GET.get('max_budget')
    year = request.GET.get('year')

    # Initialize queryset for projects and budgets
    projects = Project.objects.all().prefetch_related('accomplishment_reports__report_images')
    main_budgets = MainBudget.objects.all()

    # Get users pending approval
    pending_users = User.objects.filter(is_approved=False, is_superuser=False)

    # Get counts for sidebar
    pending_approvals_count = pending_users.count()
    active_users_count = User.objects.filter(is_approved=True, is_superuser=False).count()

    # Apply search filters
    if search_query:
        projects = projects.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(chairman__first_name__icontains=search_query) |
            Q(chairman__last_name__icontains=search_query)
        )
        main_budgets = main_budgets.filter(
            Q(chairman__first_name__icontains=search_query) |
            Q(chairman__last_name__icontains=search_query)
        )

    # Apply date filters
    if date_from:
        projects = projects.filter(start_date__gte=date_from)
    if date_to:
        projects = projects.filter(end_date__lte=date_to)

    # Apply status filter
    if status:
        today = timezone.now().date()
        if status == 'not_started':
            projects = projects.filter(start_date__gt=today)
        elif status == 'in_progress':
            projects = projects.filter(start_date__lte=today, end_date__gte=today)
        elif status == 'completed':
            projects = projects.filter(end_date__lt=today)

    # Apply budget range filters
    if min_budget:
        projects = projects.filter(allocated_budget__gte=Decimal(min_budget))
    if max_budget:
        projects = projects.filter(allocated_budget__lte=Decimal(max_budget))

    # Apply year filter
    if year:
        main_budgets = main_budgets.filter(year=year)
        projects = projects.filter(main_budget__year=year)

    # Calculate totals
    total_budget = main_budgets.aggregate(total=Sum('total_budget'))['total'] or 0
    total_expenses = projects.aggregate(total=Sum('expenses__amount'))['total'] or 0

    # Get available years for the filter dropdown
    available_years = MainBudget.objects.values_list('year', flat=True).distinct().order_by('-year')

    # Count results
    results_count = projects.count()

    context = {
        'all_projects': projects.order_by('-start_date'),
        'all_main_budgets': main_budgets.order_by('-year'),
        'total_budget': total_budget,
        'total_expenses': total_expenses,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'status': status,
        'min_budget': min_budget,
        'max_budget': max_budget,
        'selected_year': year,
        'available_years': available_years,
        'results_count': results_count,
        'pending_users': pending_users,
        'pending_approvals_count': pending_approvals_count,
        'active_users_count': active_users_count,
        'search_applied': any([search_query, date_from, date_to, status, min_budget, max_budget, year])
    }

    return render(request, 'admin_dashboard.html', context)

@login_required
def generate_comprehensive_report(request):
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="comprehensive_report.pdf"'

    # Create the PDF object using ReportLab
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    elements = []

    # Add report title
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER
    )

    # Add Republic of the Philippines and Province of Zamboanga del Sur header
    header_text_style = ParagraphStyle(
        'HeaderText',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_CENTER,
        textColor=colors.black,
        leading=14,
        spaceBefore=0,
        spaceAfter=0
    )

    elements.append(Paragraph("REPUBLIC OF THE PHILIPPINES", header_text_style))
    elements.append(Paragraph("PROVINCE OF ZAMBOANGA DEL SUR", header_text_style))
    elements.append(Paragraph("MUNICIPALITY OF DUMINGAG", header_text_style))
    elements.append(Paragraph("BARANGAY", header_text_style))
    elements.append(Spacer(1, 0.1*inch))

    # Add logos to the header
    dumingag_logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'dumingag-logo.png')

    # Create a table for the header with logos
    header_data = [[]]

    # Add Dumingag logo on the left
    if os.path.exists(dumingag_logo_path):
        try:
            # Try to load the image with PIL first to ensure it's valid
            from PIL import Image as PILImage
            pil_img = PILImage.open(dumingag_logo_path)

            # Convert to RGB if it's RGBA (transparent PNG)
            if pil_img.mode == 'RGBA':
                rgb_img = PILImage.new('RGB', pil_img.size, (255, 255, 255))
                rgb_img.paste(pil_img, mask=pil_img.split()[3])

                # Save to a temporary file
                import tempfile
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                rgb_img.save(temp_file.name, 'JPEG')
                temp_file.close()

                # Use the temporary file for ReportLab
                dumingag_logo = Image(temp_file.name)
            else:
                dumingag_logo = Image(dumingag_logo_path)

            dumingag_logo.drawWidth = 0.8*inch
            dumingag_logo.drawHeight = 0.8*inch
            header_data[0].append(dumingag_logo)
        except Exception as e:
            print(f"Error loading Dumingag logo: {str(e)}")
            header_data[0].append('')
    else:
        print(f"Dumingag logo not found at: {dumingag_logo_path}")
        header_data[0].append('')

    # Add title in the middle
    header_data[0].append(Paragraph("Comprehensive Project Report", title_style))

    # For comprehensive report, we don't have a specific user's logo, so leave it empty
    header_data[0].append('')

    # Create the header table
    header_table = Table(header_data, colWidths=[1*inch, 6.5*inch, 1*inch])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(header_table)

    # Get all chairmen and their projects
    chairmen = User.objects.filter(is_chairman=True).order_by('last_name', 'first_name')

    for chairman in chairmen:
        # Chairman header
        elements.append(Paragraph(f"Chairman: {chairman.get_full_name()}", styles['Heading2']))
        if chairman.address:
            elements.append(Paragraph(f"Address: {chairman.address}", styles['Normal']))
        elements.append(Spacer(1, 12))

        # Get chairman's projects
        projects = Project.objects.filter(chairman=chairman).order_by('name')

        if not projects:
            elements.append(Paragraph("No projects found for this chairman.", styles['Normal']))
            elements.append(Spacer(1, 12))
            continue

        # Project summary table
        project_data = [['Project Name', 'Budget', 'Total Expenses', 'Status']]
        for project in projects:
            total_expenses = project.total_expenses()
            status = "Active"
            if project.end_date < timezone.now().date():
                status = "Completed"
            elif project.start_date > timezone.now().date():
                status = "Pending"

            project_data.append([
                project.name,
                f"PHP {project.allocated_budget:,.2f}",
                f"PHP {total_expenses:,.2f}",
                status
            ])

        project_table = Table(project_data, colWidths=[250, 100, 100, 80])
        project_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BOX', (0, 0), (-1, -1), 2, colors.black),
        ]))
        elements.append(project_table)
        elements.append(Spacer(1, 20))

        # Add expense details for each project
        for project in projects:
            elements.append(Paragraph(f"Expenses for {project.name}:", styles['Heading3']))
            expenses = project.expenses.all().order_by('date_incurred')

            if not expenses:
                elements.append(Paragraph("No expenses recorded for this project.", styles['Normal']))
                elements.append(Spacer(1, 12))
                continue

            expense_data = [['Date', 'Item', 'Amount', 'Description']]
            for expense in expenses:
                expense_data.append([
                    expense.date_incurred.strftime('%Y-%m-%d'),
                    expense.item_name,
                    f"PHP {expense.amount:,.2f}",
                    expense.description
                ])

            expense_table = Table(expense_data, colWidths=[80, 150, 100, 200])
            expense_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BOX', (0, 0), (-1, -1), 2, colors.black),
            ]))
            elements.append(expense_table)
            elements.append(PageBreak())

    # Build PDF
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response

@login_required
def view_image(request, report_id, image_index):
    report = get_object_or_404(AccomplishmentReport, id=report_id)

    # Ensure user has access to this report
    if not request.user.is_superuser and report.project.chairman != request.user:
        raise Http404

    # Get all images for this report
    images = list(report.report_images.all().order_by('created_at'))

    if not images or image_index < 0 or image_index >= len(images):
        raise Http404

    current_image = images[image_index]

    context = {
        'image_url': current_image.image.url,
        'report_date': report.report_date.strftime("%B %d, %Y"),
        'caption': current_image.caption,
        'report_id': report_id,
        'has_prev': image_index > 0,
        'has_next': image_index < len(images) - 1,
        'prev_index': image_index - 1,
        'next_index': image_index + 1,
    }

    return render(request, 'partials/image_modal.html', context)









