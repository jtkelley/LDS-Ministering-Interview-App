# SMS Options for the Church App: An Admin Guide

This guide compares three major SMS services (AWS, SignalWire, and Twilio) across three setup options: 1-Way (manual replies), 1-Way with a personal number added, and 2-Way Automated Replies.

**Key Insight:** Because we are a non-profit volunteer group without an EIN and want minimal cost/hassle, the simplest and most compliant option is to use **AWS for 1-Way sending, and put a personal phone number in the message for replies.**

---

## Option 1: 1-Way Messaging (Manual Replies via a Personal Number in the Message)

This method uses the service only to send outbound messages. Replies come to a personal cell phone.

Feature	AWS SNS	SignalWire	Twilio
Setup Complexity	Low (Need an AWS account)	Medium (Need to register as Sole Prop)	Medium (Need to register as Sole Prop)
Costs (400 Msgs)	~$1.94/month (via Boto3/API)    ~$1.60 + ~$0.50/mo number fee	~$3.32 + ~$1.15/mo number fee
2-Way Messaging	Manual on a personal phone	Manual on a personal phone	Manual on a personal phone
A2P 10DLC Reg	Required (even for 1-way)	Required (Sole Prop supported)	Required (Sole Prop supported)
"STOP" Handling	Manual on a personal phone	Manual on a personal phone	Manual on a personal phone
Best For	Lowest overall cost for our volume.	Cheaper long-term rates.	Maximum reliability/documentation.
Setup Instructions (General)
Choose a Provider & Create Account: Sign up for an account (AWS is the cheapest starting point).
A2P Registration (US Only): This is mandatory for all providers. You must register your "Brand" as a "Sole Proprietor" using personal details. You must also register a "Low Volume" campaign to ensure messages deliver. This involves small one-time and recurring monthly fees.
Use the API to Send: Use the respective Python libraries (boto3, signalwire, twilio) to send messages.
Message Format: Ensure every message includes the church admin's personal number for replies:
Example: "Hi, your apt link is [link]. Call/text John at (555) 123-4567 for questions."
Option 2: 2-Way Automated Messaging (Replies Handled by the App)
This method automates reply handling (e.g., auto-confirmations, "STOP" handling) and keeps all communication within the app's system. It requires significant setup and a publicly accessible Python server.
Feature	AWS EUM/Pinpoint v2	SignalWire	Twilio
Setup Complexity	High (SNS topics, Lambda, Boto3)	High (Webhooks, Python Server)	High (Webhooks, Python Server)
Costs (400 Msgs)	~$3.94+/month (+$2 number fee + inbound msgs)	~$2.10+/month	~$4.47+/month
2-Way Messaging	Fully Automated	Fully Automated	Fully Automated
A2P 10DLC Reg	Required	Required	Required
"STOP" Handling	Automatic	Automatic	Automatic
Best For	Fully professional, automated system.	Best cost for automated system.	Most robust feature set for automation.
Setup Instructions (General & Complex)
Lease a Dedicated Number: Lease a dedicated 10-digit number or toll-free number from the provider (monthly fee applies).
A2P Registration: Complete the mandatory A2P Sole Proprietor Brand and Campaign registration.
Configure Inbound Routing:
AWS: Configure the dedicated number to publish incoming messages to an SNS Topic, which triggers an AWS Lambda function running your Python code.
SignalWire/Twilio: Set up a public-facing URL in your Python Flask/Django app that the provider can send webhooks to when a message arrives.
Code the Logic: Write the Python code to parse replies (STOP, YES, etc.) and send appropriate automated responses back via the API.
Alert Admins: Configure the Python code to send an email or SMS notification to an admin when a message arrives that requires human interaction.
Admin Recommendation Summary
For our church app's context—low volume, volunteer-run, no EIN, "neighbor" feel—Option 1 with AWS SNS offers the best balance of simplicity and cost control.
Use the free tier of AWS SNS for sending the booking links.
Add a line of text in the message providing a personal number for any questions or replies.
Avoid the complexity and recurring monthly fees of the full 2-way messaging systems.
{content: }




What are the exact Sole Proprietor registration steps on SignalWire and Twilio?

Explain the types of SMS campaigns available and which one is best for a church app

Explain the advantages of using dedicated SMS numbers over personal ones for a church app
