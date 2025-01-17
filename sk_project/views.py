from django.db import models, transaction
from django.db.models import Q, Sum
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from decimal import Decimal
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import HRFlowable
from io import BytesIO
from datetime import datetime
import os
from django.conf import settings
from .models import MainBudget, Project, User, Expense, AccomplishmentReportImage
from .forms import (
    MainBudgetForm,
    ProjectForm,
    ExpenseForm,
    AccomplishmentReportForm,
    CustomUserCreationForm,
    UserProfileForm,
    AccomplishmentReportImageForm
)
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

# User Authentication Views
def landing_page(request):
    # Get all completed projects first
    completed_projects = Project.objects.filter(
        status='completed'
    ).select_related('chairman').order_by('-end_date')[:6]
    
    projects_data = []
    for project in completed_projects:
        # Get the chairman's full address
        chairman = project.chairman
        address = chairman.address if chairman.address else "Address not available"
        
        project_info = {
            'title': project.name,
            'image': project.image or project.latest_image,
            'chairman_name': chairman.get_full_name() or chairman.username,
            'address': address,
            'completion_date': project.end_date
        }
        projects_data.append(project_info)
    
    context = {
        'completed_projects': projects_data
    }
    return render(request, 'landing_page.html', context)

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
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
                login(request, user)
                redirect_url = 'admin_dashboard' if user.is_superuser else 'dashboard'
                return JsonResponse({'success': True, 'redirect_url': reverse(redirect_url)})
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

def user_logout(request):
    logout(request)
    return redirect('landing_page')

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
    }
    return render(request, 'dashboard.html', context)

@login_required
def create_main_budget(request):
    if request.method == 'POST':
        form = MainBudgetForm(request.POST)
        if form.is_valid():
            main_budget = form.save(commit=False)
            main_budget.chairman = request.user
            main_budget.save()
            messages.success(request, 'Main budget created successfully!')
        else:
            messages.error(request, 'Error creating main budget. Please check your input.')
    return redirect('dashboard')

@login_required
def create_new_year_budget(request):
    if request.method == 'POST':
        form = MainBudgetForm(request.POST)
        if form.is_valid():
            year = form.cleaned_data['year']
            total_budget = form.cleaned_data['total_budget']
            
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
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
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
    project = get_object_or_404(Project, id=project_id, chairman=request.user)
    accomplishment_reports = project.accomplishment_reports.all().order_by('-report_date')
    
    context = {
        'project': project,
        'accomplishment_reports': accomplishment_reports,
    }
    return render(request, 'project_accomplishment_report.html', context)

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
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('dashboard')
    else:
        form = UserProfileForm(instance=request.user)
    
    return render(request, 'edit_profile.html', {'form': form})

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

    # Add a decorative header
    elements.append(Paragraph("SK Budget Report", title_style))
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
    # Get project and related data
    if request.user.is_superuser:
        project = get_object_or_404(Project, id=project_id)
    else:
        project = get_object_or_404(Project, id=project_id, chairman=request.user)
    
    expenses = project.expenses.all().order_by('-date_incurred')
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0
    remaining_budget = project.allocated_budget - total_expenses
    accomplishment_reports = project.accomplishment_reports.all().order_by('-report_date')

    # Create PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="project_{project.id}_report.pdf"'

    # Create the PDF object using letter size landscape
    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(letter),
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    # Define styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=28,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1a5f7a'),
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=18,
        spaceBefore=25,
        spaceAfter=15,
        textColor=colors.HexColor('#1a5f7a'),
        fontName='Helvetica-Bold',
        borderPadding=(0, 0, 2, 0),  # bottom border padding
        borderWidth=1,
        borderColor=colors.HexColor('#1a5f7a')
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=10,
        textColor=colors.HexColor('#2c3e50'),
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        spaceBefore=6,
        spaceAfter=6,
        textColor=colors.HexColor('#2c3e50'),
        fontName='Helvetica'
    )

    # Container for PDF elements
    elements = []

    # Add logo or header image if exists
    try:
        logo_path = os.path.join(settings.STATIC_ROOT, 'images', 'logo.png')
        if os.path.exists(logo_path):
            logo = Image(logo_path, width=100, height=100)
            logo.hAlign = 'CENTER'
            elements.append(logo)
            elements.append(Spacer(1, 20))
    except:
        pass

    # Title with decorative line
    elements.append(Paragraph(f"Project Report", title_style))
    elements.append(Paragraph(f"{project.name}", subheading_style))
    elements.append(HRFlowable(
        width="100%",
        thickness=2,
        color=colors.HexColor('#1a5f7a'),
        spaceBefore=10,
        spaceAfter=20,
        lineCap='round'
    ))

    # Project Overview Section
    elements.append(Paragraph("Project Overview", heading_style))
    
    # Project details table with better styling
    project_data = [
        ["Chairman", f"{project.chairman.get_full_name()}"],
        ["Start Date", f"{project.start_date.strftime('%B %d, %Y')}"],
        ["End Date", f"{project.end_date.strftime('%B %d, %Y')}"],
        ["Status", get_project_status(project)],
    ]
    
    t = Table(project_data, colWidths=[150, 350])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1a5f7a')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e9ecef')),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
    ]))
    elements.append(t)
    
    # Project description in a box
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("Description", subheading_style))
    description_table = Table([[project.description]], colWidths=[500])
    description_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e9ecef')),
        ('PADDING', (0, 0), (-1, -1), 15),
    ]))
    elements.append(description_table)
    elements.append(Spacer(1, 20))

    # Budget Overview Section with colorful indicators
    elements.append(Paragraph("Budget Overview", heading_style))
    
    utilization = (total_expenses/project.allocated_budget*100 if project.allocated_budget else 0)
    if utilization >= 90:
        utilization_color = colors.HexColor('#dc3545')  # red
    elif utilization >= 70:
        utilization_color = colors.HexColor('#ffc107')  # yellow
    else:
        utilization_color = colors.HexColor('#28a745')  # green
    
    budget_data = [
        ["Allocated Budget", f"₱{project.allocated_budget:,.2f}"],
        ["Total Expenses", f"₱{total_expenses:,.2f}"],
        ["Remaining Budget", f"₱{remaining_budget:,.2f}"],
        ["Budget Utilization", f"{utilization:.1f}%"],
    ]
    
    t = Table(budget_data, colWidths=[150, 350])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1a5f7a')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e9ecef')),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('TEXTCOLOR', (1, -1), (1, -1), utilization_color),  # Color the utilization percentage
        ('FONTNAME', (1, -1), (1, -1), 'Helvetica-Bold'),
    ]))
    elements.append(t)
    
    elements.append(PageBreak())

    # Expenses Section with improved table
    elements.append(Paragraph("Expenses", heading_style))
    if expenses:
        expense_data = [["Date", "Item", "Quantity", "Price per Unit", "Amount", "Description"]]
        for expense in expenses:
            expense_data.append([
                expense.date_incurred.strftime('%Y-%m-%d'),
                expense.item_name,
                str(expense.quantity),
                f"₱{expense.price_per_unit:,.2f}",
                f"₱{expense.amount:,.2f}",
                expense.description
            ])
        
        t = Table(expense_data, colWidths=[80, 100, 60, 80, 80, 150])
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5f7a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e9ecef')),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffffff')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#f8f9fa')]),
            ('ALIGN', (2, 1), (4, -1), 'RIGHT'),  # Right align numbers
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("No expenses recorded for this project.", normal_style))
    
    elements.append(PageBreak())

    # Accomplishment Reports Section with images
    elements.append(Paragraph("Accomplishment Reports", heading_style))
    
    if accomplishment_reports:
        for report in accomplishment_reports:
            # Report header with date in a colored box
            header_table = Table([[f"Report for {report.report_date.strftime('%B %d, %Y')}"]], colWidths=[500])
            header_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 14),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1a5f7a')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('PADDING', (0, 0), (-1, -1), 10),
            ]))
            elements.append(header_table)
            elements.append(Spacer(1, 10))
            
            # Report details in a box
            details_table = Table([[report.report_details]], colWidths=[500])
            details_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e9ecef')),
                ('PADDING', (0, 0), (-1, -1), 15),
            ]))
            elements.append(details_table)
            
            # Add images if they exist in a grid layout
            report_images = list(report.report_images.all())
            if report_images:
                # Create image grid (2 images per row)
                IMAGES_PER_ROW = 2
                image_rows = []
                current_row = []
                
                for image in report_images:
                    try:
                        img_path = image.image.path
                        img = Image(img_path)
                        
                        # Calculate aspect ratio and size for grid
                        img_width = 250  # Smaller width for grid layout
                        aspect = img.imageWidth / img.imageHeight
                        img_height = img_width / aspect
                        
                        # Ensure height is not too large
                        if img_height > 200:
                            img_height = 200
                            img_width = img_height * aspect
                        
                        img.drawWidth = img_width
                        img.drawHeight = img_height
                        
                        # Create caption
                        caption_text = f"Image from {report.report_date.strftime('%B %d, %Y')}"
                        if image.caption:
                            caption_text += f"\n{image.caption}"
                        
                        caption = Paragraph(
                            caption_text,
                            ParagraphStyle(
                                'Caption',
                                parent=normal_style,
                                alignment=TA_CENTER,
                                textColor=colors.HexColor('#666666'),
                                fontSize=8,
                                spaceBefore=5,
                                spaceAfter=5
                            )
                        )
                        
                        # Create a container for image and caption
                        image_container = [img, caption]
                        current_row.append(image_container)
                        
                        # Start new row when current row is full
                        if len(current_row) == IMAGES_PER_ROW:
                            image_rows.append(current_row)
                            current_row = []
                            
                    except Exception as e:
                        error_msg = Paragraph(f"Error loading image: {str(e)}", normal_style)
                        current_row.append([error_msg])
                
                # Add any remaining images in the last row
                if current_row:
                    # Pad with empty cells if needed
                    while len(current_row) < IMAGES_PER_ROW:
                        current_row.append([Paragraph('', normal_style)])
                    image_rows.append(current_row)
                
                # Create and style the image grid table
                for row in image_rows:
                    # Ensure all cells have proper flowable objects
                    for i, cell in enumerate(row):
                        if isinstance(cell, list) and len(cell) == 0:
                            row[i] = [Paragraph('', normal_style)]
                        elif isinstance(cell, str):
                            row[i] = [Paragraph(cell, normal_style)]
                    
                    grid_table = Table(
                        [row],
                        colWidths=[250] * IMAGES_PER_ROW,
                        rowHeights=[250]
                    )
                    grid_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 10),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                        ('TOPPADDING', (0, 0), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                    ]))
                    
                    elements.append(Spacer(1, 10))
                    elements.append(grid_table)
                    elements.append(Spacer(1, 10))
            
            elements.append(Spacer(1, 20))
            elements.append(HRFlowable(
                width="100%",
                thickness=1,
                color=colors.HexColor('#e9ecef'),
                spaceBefore=10,
                spaceAfter=20
            ))
    else:
        elements.append(Paragraph("No accomplishment reports available.", normal_style))

    # Build PDF with page numbers
    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.HexColor('#666666'))
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.drawRightString(doc.pagesize[0] - 40, 30, text)
        canvas.restoreState()

    doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)
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
        form = ProjectForm(request.POST, instance=project)
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
    projects = Project.objects.all()
    main_budgets = MainBudget.objects.all()
    
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
    elements.append(Paragraph("Comprehensive Project Report", title_style))

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
                f"₱{project.allocated_budget:,.2f}",
                f"₱{total_expenses:,.2f}",
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
                    f"₱{expense.amount:,.2f}",
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
