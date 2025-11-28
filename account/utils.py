import base64
from datetime import date
from decimal import Decimal
from django.utils.dateparse import parse_date
from django.contrib.contenttypes.models import ContentType
import requests

from account.models import Transaction

def encode_amount(value):
    """Convert Decimal → string → base64"""
    text = str(value)
    encoded = base64.urlsafe_b64encode(text.encode()).decode()
    return encoded

def decode_amount(encoded):
    """Convert base64 back → string → Decimal"""
    from decimal import Decimal
    decoded = base64.urlsafe_b64decode(encoded.encode()).decode()
    return Decimal(decoded)

def add_transaction(type: str, amount, status: str, user=None, related_obj=None, image=None):
    """
    Adds a transaction record to the database with today's date.
    
    Parameters:
    - type: str -> 'live_trade', 'deposit', 'withdrawal', 'trade'
    - amount: Decimal or float
    - status: str -> 'win', 'completed', 'pending', 'approved', etc.
    - user: User object (optional)
    - related_obj: Any model instance (optional) -> sets GenericForeignKey
    - image: ImageField or str path (optional)
    
    Returns:
    - Transaction object
    """
    # Ensure amount is Decimal
    if not isinstance(amount, Decimal):
        amount = Decimal(amount)

    # Prepare generic relation fields
    content_type = object_id = None
    if related_obj:
        content_type = ContentType.objects.get_for_model(related_obj)
        object_id = related_obj.pk

    transaction = Transaction.objects.create(
        type=type,
        date=date.today(),
        amount=amount,
        status=status,
        image=image or 'images/2.png',  # default if none provided
        user=user,
        content_type=content_type,
        object_id=object_id
    )
    return transaction

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def telegram(message):
    TOKEN = "8331547254:AAEg1keI4kdVggcEP78Y7j77lU3O7vWBj6c"
    chat_id = ['1322959136']

    for i in chat_id:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={i}&text={message}"
        requests.get(url)