from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def sub(value, arg):
    return value - arg

@register.filter
def multiply(value, arg):
    try:
        return Decimal(str(value)) * Decimal(str(arg))
    except (ValueError, TypeError, Decimal.InvalidOperation):
        return 0

@register.filter
def percentage(value, total):
    try:
        if total == 0:
            return 0
        return int((Decimal(str(value)) / Decimal(str(total))) * 100)
    except (ValueError, TypeError, Decimal.InvalidOperation):
        return 0

@register.filter
def sum_expenses(expenses):
    try:
        return sum(expense.amount for expense in expenses)
    except (ValueError, TypeError, AttributeError):
        return 0
def percentage(value, total):
    """Calculate percentage"""
    try:
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        if not isinstance(total, Decimal):
            total = Decimal(str(total))
        
        if total > 0:
            return round((value / total) * 100)
        return 0
    except:
        return 0

@register.filter
def sum_expenses(expenses):
    """Calculate the sum of expenses"""
    try:
        if not expenses:
            return Decimal('0')
        if isinstance(expenses, QuerySet):
            return sum(expense.amount or Decimal('0') for expense in expenses)
        return Decimal('0')
    except:
        return Decimal('0')
