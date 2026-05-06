HELP_URL = "a"


class TopErrorWindow:
    def __init__(self, HELP_URL=""):

        print(" - h=", HELP_URL or globals()["HELP_URL"])


print("HELP_URL=", HELP_URL)
w = TopErrorWindow()
HELP_URL = "qqqq"
print("HELP_URL=", HELP_URL)
w = TopErrorWindow()
