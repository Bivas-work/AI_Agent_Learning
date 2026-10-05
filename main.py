from datetime import datetime


def get_greeting(hour: int) -> str:
    """Return a greeting based on the hour of the day (0-23)."""
    if hour < 12:
        return "Good morning"
    if hour < 18:
        return "Good afternoon"
    return "Good evening"


def main() -> None:
    print("=" * 30)
    print("         Welcome!")
    print("=" * 30)

    name = input("What's your name? ").strip() or "friend"
    now = datetime.now()

    print(f"{get_greeting(now.hour)}, {name}! Today is {now:%A, %B %d, %Y}.")


if __name__ == "__main__":
    main()
