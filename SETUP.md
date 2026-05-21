# GitHub Actions Build Setup

This guide covers everything needed to get the watchOS app building and signed via GitHub Actions.

---

## 1. Export your signing certificate from Keychain Access

You need an Apple Distribution or Development certificate in your Keychain (created via the Apple Developer portal or Xcode).

1. Open **Keychain Access** on your Mac.
2. Find your certificate under **My Certificates** (it will be named something like "Apple Development: Your Name (XXXXXXXXXX)").
3. Right-click the certificate (expand the arrow first and select both the certificate and its private key - select both).
4. Choose **Export 2 items...**.
5. Save as `certificate.p12`. Choose a strong password when prompted - you will need it.

---

## 2. Base64-encode the certificate for the GitHub secret

```bash
base64 -i certificate.p12 | pbcopy
```

This copies the base64 string to your clipboard. The GitHub secret `APPLE_CERTIFICATE` will hold this value.

Store the password you chose as the secret `APPLE_CERTIFICATE_PASSWORD`.

---

## 3. Download your provisioning profile from the Apple Developer portal

1. Go to [developer.apple.com/account/resources/profiles](https://developer.apple.com/account/resources/profiles).
2. Click the **+** button to create a new profile if you do not have one.
   - Profile type: **watchOS App Development** (or Distribution for TestFlight/App Store).
   - App ID: must match bundle identifier `com.doseapp.DoseApp`.
   - Select your certificate and device(s).
3. Download the `.mobileprovision` file.

Base64-encode it:
```bash
base64 -i DoseApp.mobileprovision | pbcopy
```

The secret `APPLE_PROVISIONING_PROFILE` holds this value.

---

## 4. Add all four secrets to the GitHub repository

1. Go to your GitHub repository.
2. Click **Settings > Secrets and variables > Actions**.
3. Click **New repository secret** and add each of the following:

| Secret name                  | Value                                                 |
|------------------------------|-------------------------------------------------------|
| `APPLE_CERTIFICATE`          | Base64-encoded `.p12` file (from step 2)              |
| `APPLE_CERTIFICATE_PASSWORD` | Password chosen when exporting the certificate        |
| `APPLE_PROVISIONING_PROFILE` | Base64-encoded `.mobileprovision` file (from step 3)  |
| `APPLE_TEAM_ID`              | Your 10-character Apple Team ID (found on the portal) |

Your Team ID is visible at [developer.apple.com/account](https://developer.apple.com/account) under Membership Details.

---

## 5. Download the built IPA from GitHub Actions

1. Go to your repository on GitHub.
2. Click the **Actions** tab.
3. Click the latest successful **Build watchOS App** run.
4. Scroll to the bottom of the run page to find **Artifacts**.
5. Click **DoseApp-<sha>** to download the zip file containing the IPA.

---

## 6. Sideload via AltStore or Apple Configurator 2

### Option A - AltStore (easier, requires AltServer on a Mac/PC)

1. Install [AltServer](https://altstore.io) on your Mac or Windows PC.
2. Install AltStore on the paired iPhone (which can then relay to the paired Apple Watch).
3. Open AltStore on the iPhone, tap the **+** button, and select the `.ipa` file from the downloaded artifact.
4. AltStore signs and installs the app using your Apple ID.

Note: Free Apple ID certificates expire every 7 days and must be re-signed. A paid developer account extends this to 1 year.

### Option B - Apple Configurator 2

1. Install [Apple Configurator 2](https://apps.apple.com/app/apple-configurator-2/id1037126344) from the Mac App Store.
2. Connect your iPhone via USB and trust the Mac.
3. Drag the `.ipa` file onto the device in Configurator.
4. The app is signed with the provisioning profile embedded in the IPA (from step 3), so it must match a registered device.

---

## Troubleshooting

- **"No signing certificate found"** - make sure the certificate you exported matches the provisioning profile (same Apple ID / Team).
- **"device not registered"** - add your Apple Watch's UDID to the provisioning profile on the Developer portal and re-download it.
- **Build fails at archive step** - check the raw xcodebuild output in the Actions log (the `xcpretty || true` keeps the job going; look for `BUILD FAILED` lines above it).
