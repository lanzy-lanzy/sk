from django import forms
from .models import MainBudget, AccomplishmentReport, AccomplishmentReportImage

class MainBudgetForm(forms.ModelForm):
    class Meta:
        model = MainBudget
        fields = ['year', 'total_budget']

from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.hashers import make_password, check_password
from .models import User, RegistrationCode
from django.core.exceptions import ValidationError

class CustomUserCreationForm(UserCreationForm):
    registration_code = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full pl-10 pr-3 py-2 rounded-lg border-2 border-gray-300 focus:outline-none focus:border-tertiary transition-all duration-300 bg-gray-50 group-hover:bg-white',
            'placeholder': 'Enter registration code'
        })
    )

    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full pl-10 pr-3 py-2 rounded-lg border-2 border-gray-300 focus:outline-none focus:border-tertiary transition-all duration-300 bg-gray-50 group-hover:bg-white',
            'placeholder': 'First Name'
        })
    )

    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full pl-10 pr-3 py-2 rounded-lg border-2 border-gray-300 focus:outline-none focus:border-tertiary transition-all duration-300 bg-gray-50 group-hover:bg-white',
            'placeholder': 'Last Name'
        })
    )

    date_of_birth = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'w-full pl-10 pr-3 py-2 rounded-lg border-2 border-gray-300 focus:outline-none focus:border-tertiary transition-all duration-300 bg-gray-50 group-hover:bg-white',
            'placeholder': 'Date of Birth',
            'type': 'date'
        })
    )

    GENDER_CHOICES = [
        ('', 'Select Gender'),
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ]

    gender = forms.ChoiceField(
        choices=GENDER_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'w-full pl-10 pr-3 py-2 rounded-lg border-2 border-gray-300 focus:outline-none focus:border-tertiary transition-all duration-300 bg-gray-50 group-hover:bg-white'
        })
    )

    profile_picture = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'hidden',
            'accept': 'image/*'
        })
    )

    logo = forms.ImageField(
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'hidden',
            'accept': 'image/*'
        })
    )

    contact_number = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full pl-10 pr-3 py-2 rounded-lg border-2 border-gray-300 focus:outline-none focus:border-tertiary transition-all duration-300 bg-gray-50 group-hover:bg-white',
            'placeholder': 'Contact Number'
        })
    )

    term_of_office = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full pl-10 pr-3 py-2 rounded-lg border-2 border-gray-300 focus:outline-none focus:border-tertiary transition-all duration-300 bg-gray-50 group-hover:bg-white',
            'placeholder': 'Term of Office (e.g., 2023-2026)'
        })
    )

    address = forms.CharField(
        required=True,
        widget=forms.HiddenInput()
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email', 'first_name', 'last_name', 'date_of_birth', 'gender', 'contact_number', 'term_of_office', 'address', 'profile_picture', 'logo')

    def clean_registration_code(self):
        code = self.cleaned_data.get('registration_code')
        try:
            registration_code = RegistrationCode.objects.get(code=code)
            if not registration_code.is_valid():
                if registration_code.is_used:
                    raise ValidationError("This registration code has already been used.")
                else:
                    raise ValidationError("This registration code has expired.")
        except RegistrationCode.DoesNotExist:
            raise ValidationError("Invalid registration code. Please check and try again.")

        return code

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            from datetime import date
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age < 18:
                raise ValidationError("You must be at least 18 years old to register.")
        return dob

from django import forms
from .models import Project
from datetime import datetime

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description', 'budget', 'resolution_document', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 text-gray-700 border rounded-lg focus:outline-none focus:border-tertiary transition-colors duration-200'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 text-gray-700 border rounded-lg focus:outline-none focus:border-tertiary transition-colors duration-200'}),
            'resolution_document': forms.FileInput(attrs={'class': 'sr-only', 'accept': '.pdf,.doc,.docx'}),
        }

    def clean_start_date(self):
        start_date = self.cleaned_data.get('start_date')
        today = datetime.now().date()

        if start_date < today:
            raise forms.ValidationError("Start date must be today or a future date.")

        return start_date

    def clean_end_date(self):
        end_date = self.cleaned_data.get('end_date')
        start_date = self.cleaned_data.get('start_date')

        if not start_date:  # If start_date validation failed, skip this validation
            return end_date

        if end_date < start_date:
            raise forms.ValidationError("End date must be after the start date.")

        return end_date

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Check if the user is an admin and add additional fields
        if self.instance and self.instance.is_superuser:
            self.fields['username'] = forms.CharField(
                max_length=150,
                required=True,
                widget=forms.TextInput(attrs={
                    'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'
                }),
                initial=self.instance.username
            )
            self.fields['date_of_birth'] = forms.DateField(
                required=False,
                widget=forms.DateInput(attrs={
                    'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary',
                    'type': 'date'
                }),
                initial=self.instance.date_of_birth
            )
            self.fields['gender'] = forms.ChoiceField(
                choices=User.GENDER_CHOICES,
                required=False,
                widget=forms.Select(attrs={
                    'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'
                }),
                initial=self.instance.gender
            )
            self.fields['term_of_office'] = forms.CharField(
                max_length=20,
                required=False,
                widget=forms.TextInput(attrs={
                    'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary',
                    'placeholder': 'Term of Office (e.g., 2023-2026)'
                }),
                initial=self.instance.term_of_office
            )
            self.fields['logo'] = forms.ImageField(
                required=False,
                widget=forms.FileInput(attrs={
                    'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'
                })
            )

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

class AdminUserEditForm(forms.ModelForm):
    """Form for administrators to edit user information"""

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'date_of_birth',
                 'gender', 'contact_number', 'term_of_office', 'address', 'is_approved']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary',
                'placeholder': 'Username'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary',
                'placeholder': 'Email'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary',
                'placeholder': 'First Name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary',
                'placeholder': 'Last Name'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary',
                'type': 'date'
            }),
            'gender': forms.Select(attrs={
                'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary'
            }),
            'contact_number': forms.TextInput(attrs={
                'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary',
                'placeholder': 'Contact Number'
            }),
            'term_of_office': forms.TextInput(attrs={
                'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary',
                'placeholder': 'Term of Office (e.g., 2023-2026)'
            }),
            'address': forms.Textarea(attrs={
                'class': 'w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-tertiary',
                'placeholder': 'Address',
                'rows': 3
            }),
            'is_approved': forms.CheckboxInput(attrs={
                'class': 'h-5 w-5 text-tertiary focus:ring-tertiary border-gray-300 rounded'
            }),
        }
