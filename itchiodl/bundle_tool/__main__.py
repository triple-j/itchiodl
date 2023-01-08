from getpass import getpass
import itchiodl
from itchiodl.logging import configLogging


def main():
    configLogging()

    user = input("Username: ")
    password = getpass("Password: ")

    l = itchiodl.LoginWeb(user, password)

    url = input("Bundle URL: ")
    b = itchiodl.Bundle(l, url)
    b.load_games()


if __name__ == "__main__":
    main()
