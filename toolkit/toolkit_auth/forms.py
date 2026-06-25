from django.contrib.auth.forms import AuthenticationForm


class EmailOrUsernameAuthForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Username or email"
        self.fields["username"].widget.attrs["autocomplete"] = "username"
        self.fields["username"].widget.attrs["aria-describedby"] = "username_error"
        self.fields["password"].widget.attrs["autocomplete"] = "current-password"
        self.fields["password"].widget.attrs["aria-describedby"] = "password_error"
