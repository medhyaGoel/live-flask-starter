import smtplib

email = 'paybac.app@gmail.com'  # Your email
password = ''  # Your email account password
send_to_email = ''  # Who you are sending the message to
file_location = "follow-ups.txt"


# Initialize SMTP server
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login(email, password)

# Open the file and read its content
with open(file_location) as f:
    # Read the content line by line
    lines = f.readlines()

# Initialize variables to store email content and subject
email_content = ""
subject = ""

# Flag to indicate whether to start processing emails
start_processing_emails = False

# Iterate through the lines of the file
for line in lines:
    # Check if the line starts with 'Subject:'
    if line.startswith('Subject:'):
        # Extract the subject from the line
        subject = line[len('Subject:'):].strip()
    # Check if the line is 'EMAILS:'
    elif line.strip() == 'EMAILS:':
        # Set flag to start processing emails
        start_processing_emails = True
    # Continue only if flag is set and line is not empty
    elif start_processing_emails and line.strip():
        # Append non-empty lines to the email content
        email_content += line

# Construct the email content
text = f"Subject: {subject}\n\n{email_content}"

# Send the email
server.sendmail(email, send_to_email, text)

# Close the SMTP server connection
server.quit()
