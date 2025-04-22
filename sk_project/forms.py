from django import forms
from .models import MainBudget, AccomplishmentReport, AccomplishmentReportImage

class MainBudgetForm(forms.ModelForm):
    class Meta:
        model = MainBudget
        fields = ['year', 'total_budget']

from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.hashers import make_password, check_password
from .models import User

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)

from django import forms
from .models import Project

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description', 'budget', 'start_date', 'end_date']

from django import forms
from .models import Expense

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['item_name', 'price_per_unit', 'quantity', 'description', 'amount', 'date_incurred']
        widgets = {
            'item_name': forms.TextInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'price_per_unit': forms.NumberInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'quantity': forms.NumberInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'description': forms.TextInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'amount': forms.NumberInput(attrs={
                'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary',
                'inputmode': 'numeric',
                'pattern': '[0-9]*',
                'onkeyup': 'this.value=this.value.replace(/\\B(?=(\\d{3})+(?!\\d))/g, ",").replace(/^0+/, "")'
            }),
            'date_incurred': forms.DateInput(attrs={'type': 'date', 'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
        }

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class AccomplishmentReportForm(forms.ModelForm):
    class Meta:
        model = AccomplishmentReport
        fields = ['report_date', 'report_details']
        widgets = {
            'report_date': forms.DateInput(attrs={'type': 'date'}),
            'report_details': forms.Textarea(attrs={'rows': 4}),
        }

class AccomplishmentReportImageForm(forms.Form):
    images = forms.FileField(
        widget=MultipleFileInput(attrs={'class': 'sr-only', 'accept': 'image/*', 'multiple': True}),
        required=False
    )

from django import forms
from .models import Profile
from django import forms
from .models import User
from django import forms
from .models import User

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'profile_picture', 'address', 'contact_number']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'email': forms.EmailInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
            'contact_number': forms.TextInput(attrs={'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'}),
        }

class CustomPasswordChangeForm(PasswordChangeForm):
    """Custom form for changing password with enhanced security"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add custom styling to the form fields
        self.fields['old_password'].widget.attrs.update({
            'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary',
            'placeholder': 'Enter your current password'
        })
        self.fields['new_password1'].widget.attrs.update({
            'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary',
            'placeholder': 'Enter new password'
        })
        self.fields['new_password2'].widget.attrs.update({
            'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary',
            'placeholder': 'Confirm new password'
        })
