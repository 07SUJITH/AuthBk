from decouple import config
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
    
    Usage in production:
    1. Set environment variables with superuser credentials
    2. Run this command during deployment
    3. Remove environment variables after successful superuser creation
    """
    help = 'Creates an initial superuser non-interactively if one does not exist.'

    def handle(self, *args, **options):
        User = get_user_model()
        superuser_email = config('DJANGO_SUPERUSER_EMAIL')
        superuser_password = config('DJANGO_SUPERUSER_PASSWORD')

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
            else:
                self.stdout.write(self.style.WARNING(f'Superuser with email "{superuser_email}" already exists. Skipping creation.'))
        except IntegrityError:
            self.stdout.write(self.style.WARNING(f'Superuser with email "{superuser_email}" already exists (IntegrityError). Skipping creation.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating superuser: {e}'))