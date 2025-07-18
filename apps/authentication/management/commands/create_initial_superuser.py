import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import IntegrityError


class Command(BaseCommand):
    """
    Creates an initial superuser non-interactively using environment variables.
    
    This command is designed for initial project setup in environments without shell access,
    particularly in free-tier hosting platforms. After successful superuser creation,
    it's recommended to remove the superuser credentials from environment variables
    for security reasons.
    
    Required environment variables:
    - DJANGO_SUPERUSER_EMAIL: Email for the superuser
    - DJANGO_SUPERUSER_PASSWORD: Password for the superuser
    """
    help = 'Creates an initial superuser non-interactively if one does not exist.'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # Try to get from environment first, then fall back to python-decouple
        superuser_email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        superuser_password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        
        # Log the environment variables we found (without sensitive data)
        self.stdout.write(self.style.NOTICE('Environment:'))
        self.stdout.write(self.style.NOTICE(f'- DJANGO_SUPERUSER_EMAIL: {"Set" if superuser_email else "Not set"}'))
        self.stdout.write(self.style.NOTICE(f'- DJANGO_SUPERUSER_PASSWORD: {"Set" if superuser_password else "Not set"}'))

        if not superuser_email or not superuser_password:
            self.stdout.write(self.style.ERROR(
                'Error: DJANGO_SUPERUSER_EMAIL or DJANGO_SUPERUSER_PASSWORD environment variables not set.\n'
                'This command requires both environment variables to be set with valid credentials.\n'
                'Please set these variables in your deployment environment and try again.\n'
                'Note: After successful superuser creation, it is recommended to remove these\n'
                'environment variables for security reasons.'
            ))
            return

        try:
            if not User.objects.filter(email=superuser_email).exists():
                user = User.objects.create_superuser(
                    email=superuser_email,
                    password=superuser_password
                )
                self.stdout.write(self.style.SUCCESS(f'Superuser "{user.email}" created successfully.'))
                self.stdout.write(self.style.SUCCESS('Please remove the superuser credentials from environment variables for security.'))
            else:
                self.stdout.write(self.style.WARNING(f'Superuser with email "{superuser_email}" already exists. Skipping creation.'))
        except IntegrityError as e:
            self.stdout.write(self.style.WARNING(f'IntegrityError creating superuser: {e}'))
            self.stdout.write(self.style.WARNING(f'Superuser with email "{superuser_email}" may already exist.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Unexpected error creating superuser: {e}'))
            self.stdout.write(self.style.ERROR('Please check your database connection and settings.'))