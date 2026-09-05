# ApplyJin Chrome Extension

Auto-fill job applications with your tailored resume from ApplyJin.

## Install (Developer Mode)

1. Open `chrome://extensions/`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked**
4. Select the `extension/` directory
5. Pin the extension to your toolbar

## Setup

1. Click the extension icon on any page
2. Go to **Settings** tab
3. Enter your ApplyJin backend URL (e.g., `https://your-app.onrender.com`)
4. Optionally paste your JWT auth token from the dashboard

## Usage

### Autofill tab
- Scans the current page for form fields
- Detects field types (name, email, phone, etc.)
- Click **Fill all fields** to auto-fill with your resume data

### Extract JD tab
- Extracts job title, company, and description from the page
- Supports LinkedIn, Greenhouse, Lever, Workday, and generic job boards
- Click **Score this JD** to run ghost-job scoring via the backend

### Settings tab
- Configure backend URL and auth token
- Connection status shown in header (green dot = connected)

## Privacy

- All data stays on your machine and your ApplyJin backend
- No data is sent to third parties
- The extension only runs when you click the icon
