# CWE-798: Hardcoded Credentials — fake secrets for Snyk Secret scan testing only.
REDIS_PASSWORD = "r3d1s-Pa55w0rd-D0Nt-Us3"
SMTP_URL = "smtp://mailer:H0rr1blePassw0rd@smtp.internal:587"


def main():
    print("Hello from simple-no-deps!")


if __name__ == "__main__":
    main()
