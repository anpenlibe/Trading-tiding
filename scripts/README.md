# 🛠️ Scripts Directory

**Utility Scripts for System Setup and Maintenance**  
**Purpose**: Helper scripts for system configuration and external API management  
**Target Users**: Developers and system administrators  

---

## 📂 Scripts Overview

```
scripts/
└── generate_zerodha_token.py  ← Automated Zerodha OAuth token generation
```

---

## 🔑 generate_zerodha_token.py - Zerodha OAuth Token Generator

**Purpose**: Automated generation of Zerodha access tokens through OAuth flow  
**Use Case**: Initial setup and periodic token renewal for live data access  
**Status**: Production ready with automated browser handling  

### Key Features
- **Automated OAuth Flow**: Handles complete Zerodha login and token exchange
- **Browser Integration**: Launches browser automatically for user authentication
- **Secure Token Storage**: Saves tokens securely to environment configuration
- **Error Handling**: Comprehensive error handling for OAuth failures
- **User-Friendly**: Simple CLI interface with clear instructions

### When You Need This Script

#### **Initial Setup (First Time)**
```bash
# When setting up system for live trading
python scripts/generate_zerodha_token.py
```

#### **Token Renewal (Periodic)**
Zerodha access tokens expire and need renewal:
- **Frequency**: Tokens typically expire daily or when manually revoked
- **Symptoms**: Data collection failures, API authentication errors
- **Solution**: Re-run the token generation script

```bash
# When you see "Token expired" or "Unauthorized" errors
python scripts/generate_zerodha_token.py
```

### Usage Instructions

#### **Prerequisites**
1. **Zerodha Account**: Active Zerodha trading account
2. **Kite Connect App**: Register for API access at https://kite.trade
3. **API Credentials**: API Key and API Secret from Kite Connect dashboard

#### **Configuration Setup**
```bash
# Add to .env file (get from Zerodha Kite Connect dashboard)
ZERODHA_API_KEY=your_api_key_here
ZERODHA_API_SECRET=your_api_secret_here
```

#### **Running the Script**
```bash
# Run the token generator
cd /path/to/trading-tiding
python scripts/generate_zerodha_token.py

# The script will:
# 1. Read API credentials from .env
# 2. Launch your browser to Zerodha login page
# 3. Wait for you to complete login and authorization
# 4. Capture the access token automatically
# 5. Save the token to your configuration
```

### Step-by-Step Process

#### **1. Script Initialization**
```bash
$ python scripts/generate_zerodha_token.py

🔑 Zerodha Token Generator
==========================
✅ API Key found: xxxxxx
✅ API Secret found: xxxxxx
🌐 Starting OAuth flow...
```

#### **2. Browser Authentication**
- Browser opens to Zerodha login page
- **User action required**: Log in with your Zerodha credentials
- Authorize the Kite Connect application
- Browser redirects to token capture page

#### **3. Automatic Token Capture**
```bash
🎯 Waiting for authorization...
✅ Token received: yyyyyy
💾 Saving token to configuration...
✅ Token saved successfully!

Your Zerodha access token is now configured.
You can now use live data in your trading system.
```

#### **4. Verification**
```bash
# Verify token works
python apps/data_collector.py --symbols RELIANCE --test
```

### Configuration Output

The script automatically updates your configuration:

#### **Environment File (.env)**
```bash
# Zerodha API Configuration
ZERODHA_API_KEY=your_api_key
ZERODHA_API_SECRET=your_api_secret
ZERODHA_ACCESS_TOKEN=generated_access_token  # ← Added by script
```

#### **Script Environment (scripts/.env)**
```bash
# Token generation specific settings
ZERODHA_API_KEY=your_api_key
ZERODHA_API_SECRET=your_api_secret
REDIRECT_URL=http://localhost:3000/callback
```

### Technical Details

#### **OAuth Flow Implementation**
```python
# The script implements standard OAuth 2.0 flow:
1. Generate authorization URL with API credentials
2. Launch browser to authorization URL
3. User completes login and grants permissions
4. Zerodha redirects to localhost callback with request token
5. Exchange request token for access token using API secret
6. Save access token for system use
```

#### **Security Features**
- **Local callback server**: Runs on localhost:3000 for token capture
- **Automatic cleanup**: Server shuts down after token capture
- **No token exposure**: Tokens never logged or displayed in plain text
- **Environment isolation**: Uses separate .env for script-specific settings

#### **Error Handling**
```python
# Common error scenarios handled:
- Missing API credentials
- Network connectivity issues
- Invalid API credentials
- User canceling authorization
- Token exchange failures
- Server startup failures
```

### Troubleshooting

#### **Common Issues and Solutions**

| **Issue** | **Symptoms** | **Solution** |
|-----------|-------------|-------------|
| **Missing API credentials** | "API key not found" error | Add `ZERODHA_API_KEY` and `ZERODHA_API_SECRET` to `.env` |
| **Browser doesn't open** | Script hangs at "Starting OAuth flow" | Manually open the displayed URL in browser |
| **Port already in use** | "Address already in use" error | Kill process using port 3000 or restart system |
| **Token capture timeout** | "Waiting for authorization..." hangs | Complete authorization in browser within 5 minutes |
| **Invalid credentials** | "Invalid API key" from Zerodha | Verify API credentials in Kite Connect dashboard |

#### **Manual Token Generation**
If the automated script fails, you can generate tokens manually:

```python
# Manual token generation process:
1. Visit: https://kite.trade/connect/login?api_key=YOUR_API_KEY
2. Complete login and authorization
3. Copy request_token from redirect URL
4. Use request_token to generate access_token via API
```

### Usage in Trading System

Once the token is generated, the trading system automatically uses it:

#### **Data Collection**
```python
# System automatically uses the token for live data
python apps/data_collector.py  # Uses Zerodha API with token

# Falls back to mock data if token invalid
python apps/data_collector.py  # Automatically falls back on errors
```

#### **Trading Applications**
```python
# All applications can use live data when token is configured
python apps/trader.py      # Live market data
python apps/backtest.py    # Can collect fresh data
python apps/monitor.py     # Real-time data monitoring
```

### Token Management

#### **Token Lifecycle**
- **Generation**: Use this script when setting up or renewing
- **Storage**: Stored securely in .env file
- **Usage**: Automatically used by data collection components
- **Expiry**: Tokens expire periodically (daily or on revocation)
- **Renewal**: Run script again when tokens expire

#### **Monitoring Token Health**
```bash
# Check if token is working
python apps/data_collector.py --test

# Monitor for token expiry in logs
tail -f data/logs/data_collector.log | grep -i "unauthorized\|token\|expired"

# System health check includes token validation
python apps/health_check.py
```

---

## 🔧 Integration with Main System

### **System Configuration Impact**
The token generator integrates with the main system configuration:

```python
# src/data/config.py automatically uses the generated token
ZERODHA_ACCESS_TOKEN = os.getenv('ZERODHA_ACCESS_TOKEN')

# src/data/data_sources.py uses the token for API calls
class ZerodhaAPI:
    def __init__(self):
        self.kite = KiteConnect(api_key=ZERODHA_API_KEY)
        self.kite.set_access_token(ZERODHA_ACCESS_TOKEN)  # Uses generated token
```

### **Fallback Behavior**
```python
# System gracefully handles missing or invalid tokens:
try:
    # Attempt to use Zerodha API with token
    data = zerodha_api.fetch_ohlc(symbol)
except Exception as e:
    logger.warning(f"Zerodha API failed: {e}")
    # Automatically fall back to Mock API
    data = mock_api.fetch_ohlc(symbol)
```

---

## 📋 Maintenance and Best Practices

### **Regular Maintenance**
- **Weekly**: Check token health during system monitoring
- **Monthly**: Proactively regenerate tokens to avoid expiry issues
- **Quarterly**: Review API credentials and access permissions

### **Security Best Practices**
- **Never commit tokens**: Tokens should only be in .env file (gitignored)
- **Regenerate regularly**: Don't wait for expiry, regenerate proactively
- **Monitor usage**: Track API usage to detect unauthorized access
- **Secure environment**: Ensure .env file has proper permissions (600)

### **Deployment Considerations**
```bash
# Production deployment token generation
1. Set up API credentials in production .env
2. Run token generation on production server
3. Verify token works with test data collection
4. Monitor logs for authentication issues
5. Set up automated token renewal (cron job)
```

---

## 🔗 Related Documentation

- **[System Architecture](../SYSTEM_ARCHITECTURE.md)**: Token management in system architecture
- **[Data Layer](../src/data/README.md)**: How tokens are used in data collection
- **[Configuration](../src/data/README.md)**: Environment variable management
- **[Applications](../apps/README.md)**: How applications use live data with tokens

---

**🔑 The Zerodha token generator is essential for live trading data. Run it whenever you need to access real market data from the NSE through Zerodha's API.**