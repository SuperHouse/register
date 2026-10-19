from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

hex_colour_validator = RegexValidator(r'^#[0-9a-fA-F]{6}$', 'Enter a colour as # and six hex digits, e.g. #3c4b64.')
hostname_validator = RegexValidator(
    r'^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$',
    'Enter a hostname only, e.g. serials.example.com (no https://, path or port).',
)


class Org(models.Model):
    company_name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='clients/', null=True, blank=True)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL)

    is_client = models.BooleanField(default=True)
    is_manufacturer = models.BooleanField(default=False)
    is_supplier = models.BooleanField(default=False)


    def __str__(self):
        return self.company_name

    @classmethod
    def get_clients(cls):
        return cls.objects.filter(is_client=True)

    @classmethod
    def get_manufacturers(cls):
        return cls.objects.filter(is_manufacturer=True)

    @classmethod
    def get_suppliers(cls):
        return cls.objects.filter(is_supplier=True)


class BrandedHost(models.Model):
    """A client's vanity hostname, and how the site looks when it is reached through it (issue #150).

    Branding is cosmetic only: it changes the logo, name and colours, never what data a
    user can see. Setting the hostname up on the server (DNS, Caddy, ALLOWED_HOSTS) is a
    separate step - see docs/admin/deployment.md.
    """

    hostname = models.CharField(max_length=253, unique=True, validators=[hostname_validator])
    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name='branded_hosts')
    display_name = models.CharField(
        max_length=100, help_text='Shown in page titles and emails, e.g. "Example Co". Defaults to the company name.',
        blank=True,
    )
    # Stored under branding/, which conf/media.py serves to everyone: the login page shows
    # this logo to people who are not logged in yet.
    logo = models.ImageField(upload_to='branding/')
    logo_link_url = models.URLField(
        blank=True, help_text='Where clicking the logo goes, e.g. the client\'s website. Defaults to the dashboard.',
    )
    sidebar_colour = models.CharField(
        max_length=7, blank=True, validators=[hex_colour_validator],
        help_text='Sidebar background, e.g. #3c4b64. Text colour is chosen automatically. Blank for the default.',
    )
    accent_colour = models.CharField(
        max_length=7, blank=True, validators=[hex_colour_validator],
        help_text='Buttons, links and table headers, e.g. #321fdb. Blank for the default.',
    )

    class Meta:
        ordering = ['hostname']

    def __str__(self):
        return self.hostname

    def save(self, *args, **kwargs):
        self.hostname = self.hostname.strip().lower()
        self.sidebar_colour = self.sidebar_colour.lower()
        self.accent_colour = self.accent_colour.lower()
        super().save(*args, **kwargs)

    @property
    def brand_name(self):
        return self.display_name or self.org.company_name

