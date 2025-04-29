from .models import User, Project

def user_info(request):
    """
    Context processor to add user information to all templates.
    """
    context = {}

    if request.user.is_authenticated:
        # For regular users
        context['user_address'] = request.user.address
        context['user_contact_number'] = request.user.contact_number
        context['user_term_of_office'] = request.user.term_of_office

        # Debug information
        print(f"Context processor - User: {request.user.username}, Address: {request.user.address}")

        # For admin users
        if request.user.is_superuser:
            # Count pending approvals
            context['pending_approvals_count'] = User.objects.filter(is_approved=False, is_superuser=False).count()
            # Count active users
            context['active_users_count'] = User.objects.filter(is_approved=True, is_superuser=False).count()
            # Get all projects for admin
            context['all_projects'] = Project.objects.all()
        else:
            # Get user's projects
            context['all_projects'] = Project.objects.filter(chairman=request.user)

    return context
