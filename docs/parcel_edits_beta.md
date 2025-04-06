# ParcelApp Integration Guide (Beta)

This guide explains how to set up and use the ParcelApp integration in Home Assistant.

---

## Step 1: Retrieve Your Account Token

1. Navigate to the [ParcelApp Web Login Page](https://web.parcelapp.net/).
2. Sign in with your credentials.
3. Open the **Developer Tools** in your browser (right-click anywhere on the page and select **Inspect**).
4. Go to the **Network** tab.
5. Refresh the page.
6. Look for a network event labeled `message=logged` (this is usually the first event after logging in).
7. Under **Request Headers**, locate the `Cookie` field and find the value for `account_token` (e.g., `account_token=_TOKEN_HERE`).
8. Copy the token and input it into the Home Assistant configuration under `account_token`.  
   **Note**: There is no validation step for this token.

---

## Step 2: Example: Add a Parcel Using Home Assistant

1. Open Home Assistant and navigate to **Developer Tools**.
2. Click on the **Services** tab.
3. Find the service `parcelapp.add_parcel`.
4. Fill out the required fields:
   - **Name**: The name of the package (e.g., "My Package").
   - **Number**: The tracking number for the package.
   - **Courier**: The courier code (e.g., `ups` for UPS). Found in [this link](https://api.parcel.app/external/supported_carriers.json)
5. Fire the service.

---

## Step 3: Check the Logs

- After firing the service, check the Home Assistant logs for the result:
  - **ADDED**: The parcel was successfully added.
  - **DUPLICATE**: The tracking number already exists.
  - **ERROR**: An error occurred during the process.

---

## Notes

- Ensure the `account_token` is correctly configured in your Home Assistant setup.
- Courier codes are case-sensitive and must match the expected format (e.g., `ups`, etc.).
- This is a beta feature, so some functionality may be subject to change.