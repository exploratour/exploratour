class ValidationError(Exception):
    """Exception raised when invalid parameters were supplied to a form.

    """
    def __init__(self, errormsg):
        self.errormsg = errormsg

    def __str__(self):
        return "ValidationError(%s)" % self.errormsg
