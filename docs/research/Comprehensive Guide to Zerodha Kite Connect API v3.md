<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" class="logo" width="120"/>

# Comprehensive Guide to Zerodha Kite Connect API v3 in 2025

## Overview and Core Capabilities

Zerodha's Kite Connect API v3 is a comprehensive set of REST-like HTTP APIs that provide extensive capabilities for building complete stock market investment and trading platforms[^1]. The API enables real-time order execution across equities, commodities, and mutual funds, portfolio management, and live market data streaming through WebSockets[^1].

The current stable version remains **v3**, with all requests defaulting to this version[^1]. For production applications, it's recommended to explicitly request this version by setting the HTTP header `X-Kite-version: 3`[^1]. The root API endpoint is `https://api.kite.trade`[^1].

## Authentication and Session Management

### Login Flow and Token Management

The authentication process follows a secure three-step flow[^2]:

1. Navigate to the public Kite login endpoint: `https://kite.zerodha.com/connect/login?v=3&api_key=xxx`[^2]
2. Upon successful login, receive a `request_token` as a URL query parameter[^2]
3. POST the `request_token` and `checksum` (SHA-256 of `api_key + request_token + api_secret`) to `/session/token` to obtain an `access_token`[^2]

### Session Validity and Limitations

Access tokens are valid throughout the trading day once created, typically expiring around 7:00 AM to 7:30 AM the following day[^45]. Only one active access token per API key is permitted, and generating a new token invalidates the previous one[^45]. There's a dependency between Kite web sessions and API sessions - logging into Kite web after creating an API session may invalidate the API token[^45].

## Rate Limits and Restrictions

### Order Placement Limits

Zerodha implements several risk management measures through rate limiting[^6][^40]:

- **Daily limit**: Maximum 3,000 orders per day across all segments[^6][^40]
- **Per-minute limit**: Maximum 200 orders per minute[^40]
- **Order modifications**: Maximum 25 modifications allowed per order[^40]


### API Request Rate Limits

The API enforces specific rate limits for different types of requests[^39][^42]:

- **General GET calls**: Maximum 10 requests per second[^39]
- **Historical data API**: Limited to 3 requests per second[^39][^42]
- **Order placement API**: 5-10 requests per second, restricted to 200 order placements per minute[^42]

When the rate limit of 429 (Too many requests) is encountered, applications should implement appropriate backoff strategies[^38].

## Supported Order Types and Varieties

### Order Varieties

Kite Connect supports multiple order varieties[^17]:


| Variety | Description |
| :-- | :-- |
| `regular` | Standard regular orders |
| `amo` | After Market Orders |
| `co` | Cover Orders (discontinued since March 2020)[^37] |
| `iceberg` | Iceberg Orders for large quantity splitting[^22] |
| `auction` | Auction Orders |

### Order Types

The API supports comprehensive order types[^17][^18]:


| Order Type | Description |
| :-- | :-- |
| `MARKET` | Market orders executed at current best available price[^18] |
| `LIMIT` | Limit orders with specified price constraints[^18] |
| `SL` | Stop-loss orders for risk management[^18] |
| `SL-M` | Stop-loss market orders[^18] |

### Product Types

Different product categories are supported[^17]:

- **CNC**: Cash \& Carry for equity
- **NRML**: Normal for futures and options
- **MIS**: Margin Intraday Squareoff
- **MTF**: Margin Trading Facility


### Advanced Order Features

#### Iceberg Orders

Iceberg orders slice large orders into smaller parts, with each leg sent to the exchange only after the previous order fills[^22]. This feature helps reduce impact costs and prevents revealing large orders in market depth[^22]. Iceberg orders are available for NSE equity, F\&O, currency, and BSE equity, but cannot be used with market and SL-M orders[^22].

#### GTT (Good Till Triggered) Orders

GTT orders remain active until trigger conditions are met, with validity of one year[^30][^31]. The API supports both single-leg triggers and OCO (One Cancels Other) configurations for simultaneous target and stop-loss placement[^33].

## WebSocket Streaming Capabilities

### Connection Specifications

The WebSocket API provides the most efficient method for receiving live market data[^7]. Key specifications include:

- **Endpoint**: `wss://ws.kite.trade`[^7]
- **Subscription limit**: Up to 3,000 instruments per connection[^7][^13]
- **Connection limit**: Maximum 3 WebSocket connections per API key[^7][^13]
- **Total capacity**: Up to 9,000 instruments across all connections[^13]


### Streaming Modes

Three distinct streaming modes are available[^7]:


| Mode | Description | Packet Size |
| :-- | :-- | :-- |
| `ltp` | Last Traded Price only | 8 bytes |
| `quote` | Multiple fields excluding market depth | 44 bytes |
| `full` | Complete data including 5-level market depth | 184 bytes |

### Data Types and Features

WebSocket streams deliver multiple data types[^7]:

- **Market data**: Binary format with real-time quotes, OHLC, volume, and market depth
- **Order updates**: Real-time order status changes and postbacks
- **Text messages**: Alerts and notifications from the broker
- **Heartbeat**: 1-byte signals to maintain connection when no data flows


## Recent Updates and New Features (2025)

### Kite Connect Personal APIs

A significant development in 2025 is the introduction of **Kite Connect Personal APIs**, offering free access to essential trading functionalities[^11][^15]. This free tier includes:

- Full-fledged order, GTT, and alerts management[^35]
- Margin computation and portfolio management[^35]
- Excludes market data, requiring users to have alternative data sources[^11][^15]


### Order Slicing Enhancement

Automatic order slicing has been implemented to handle large orders that exceed exchange freeze limits[^11][^15]. When orders surpass limits, they're automatically divided into smaller parts - for example, large Nifty orders can be split into up to 20 slices of 1,800 quantities each[^19].

### Market Protection Feature

A new market protection feature makes market orders safer by preventing execution at unexpected prices during volatile market conditions[^19]. This addresses concerns about orders executing at unfavorable prices during high volatility periods.

## API Pricing Structure

### Current Pricing Tiers (2025)

Zerodha offers a tiered pricing structure[^35][^41]:


| Tier | Cost | Features |
| :-- | :-- | :-- |
| **Personal (Free)** | Free | Order management, GTT, portfolio management (no market data)[^35] |
| **Connect** | ₹500/month | Everything in Personal plus real-time WebSocket data and historical candles[^35] |
| **Enterprise** | Custom | For startups and mass retail products, potentially free with partnership[^35] |

## Community-Built Python Libraries and Wrappers

### Official Libraries

Zerodha provides official libraries across multiple programming languages[^1][^27]:

- **Python**: Official PyKiteConnect library[^3][^23]
- **Go**: Official Go client[^9]
- **Java**: Official Java client[^4]
- **Node.js**: Official TypeScript/JavaScript client[^5]
- **.NET/C\#**: Official .NET library[^27]
- **PHP**: Official PHP library[^27]


### Community and Enhanced Python Libraries

Several community-built Python libraries enhance Kite Connect functionality:

#### 1. Enhanced Kite API Wrapper

The **Kite-API-Mod** by Niteshkpatel provides convenient wrapper functionality with automated OTP handling[^25]:

- Automatic login process with OTP integration using `pyotp`[^25]
- Simplified order placement and management[^25]
- Enhanced error handling and session management[^25]


#### 2. QuantWorks Framework

**QuantWorks** by Cranial490 offers a comprehensive Python wrapper for testing and deploying trading strategies[^29]:

- Automated login flow using Selenium[^29]
- Built-in backtesting capabilities with historical data fetching[^29]
- Live market tick streaming integration[^29]
- Position management utilities for strategy development[^29]


#### 3. Algo Trading Templates

The **Python-Algo-Trading-Zerodha** repository by QuickLearner171998 provides sample strategy templates[^36]:

- PSAR (Parabolic SAR) based trading strategies[^36]
- Automated login process with Selenium integration[^36]
- Utility functions for common trading operations[^36]


### Integration Examples and Usage

Community libraries typically focus on:

- **Automated authentication**: Handling the complex login flow programmatically[^29][^36]
- **Strategy backtesting**: Providing frameworks for testing trading algorithms[^29][^36]
- **Enhanced error handling**: Improved exception management beyond official libraries[^25]
- **Simplified API calls**: Wrapper functions that reduce complexity for common operations[^25]


## Error Handling and Exception Management

### Common Exception Types

The API defines specific exception types for different error scenarios[^38]:


| Exception | Description |
| :-- | :-- |
| `TokenException` | Session expiry or invalidation (HTTP 403)[^38] |
| `OrderException` | Order placement failures or corrupt fetches[^38] |
| `MarginException` | Insufficient funds for order placement[^38] |
| `NetworkException` | Communication errors with OMS[^38] |
| `InputException` | Missing or invalid parameters[^38] |

### HTTP Status Codes

Standard HTTP codes indicate various states[^38]:

- **400**: Bad request parameters
- **403**: Session expired, requires re-login
- **429**: Rate limiting exceeded
- **500**: Internal server errors
- **502**: Backend OMS unavailable


## Historical Data and Market Information

### Data Access Limitations

Historical data API is available as an add-on to the main Connect subscription[^42]. The service provides:

- **Data coverage**: Several years of historical data across all instruments[^42]
- **Data format**: OHLC with volume and open interest in candle format[^42]
- **Time intervals**: Multiple timeframes including 1-minute, 5-minute, 15-minute, hourly, and daily[^21]
- **Rate limits**: 3 requests per second for historical data endpoints[^39][^42]


### Quote APIs

Real-time market data access through dedicated quote endpoints[^10]:

- `/quote`: Complete market quotes including depth for up to 500 instruments[^10]
- `/quote/ohlc`: OHLC quotes for up to 1,000 instruments[^10]
- `/quote/ltp`: Last traded price for up to 1,000 instruments[^10]


## Conclusion

Zerodha's Kite Connect API v3 continues to evolve in 2025 with significant enhancements including free Personal APIs, automatic order slicing, and improved market protection features[^11][^15]. The robust WebSocket streaming capabilities support up to 9,000 concurrent instrument subscriptions across multiple connections[^7][^13].

The comprehensive rate limiting system ensures stable operation with 3,000 daily order limits and various per-second restrictions[^6][^39][^40]. Community-built Python libraries like QuantWorks, Kite-API-Mod, and various algo trading templates provide enhanced functionality beyond the official libraries, particularly focusing on automated authentication and strategy development[^25][^29][^36].

For developers building trading applications, the combination of official libraries and community enhancements offers a robust foundation for algorithmic trading, portfolio management, and market data analysis within the Indian capital markets ecosystem.

<div style="text-align: center">⁂</div>

[^1]: https://kite.trade/docs/connect/v3/

[^2]: https://kite.trade/docs/connect/v3/user/

[^3]: https://github.com/zerodha/pykiteconnect

[^4]: https://github.com/zerodha/javakiteconnect

[^5]: https://www.npmjs.com/package/kiteconnect

[^6]: https://support.zerodha.com/category/trading-and-markets/kite-web-and-mobile/kite-error-messages/articles/order-rate-limits-on-kite

[^7]: https://kite.trade/docs/connect/v3/websocket/

[^8]: https://stackoverflow.com/questions/42086868/python-code-for-zerodha-kite-connect-api

[^9]: https://github.com/zerodha/gokiteconnect

[^10]: https://kite.trade/docs/connect/v3/changelog/

[^11]: https://zerodha.com/z-connect/updates/zerodha-q1-2025-major-updates-you-should-know

[^12]: https://www.youtube.com/watch?v=lJJJcYuVwQI

[^13]: https://kite.trade/forum/discussion/11179/how-many-websocket-connection-per-kite-connect-app

[^14]: https://www.youtube.com/watch?v=9vzd289Eedk

[^15]: https://zerodha.com/z-connect/updates

[^16]: https://zerodha.com/z-connect/business-updates/whats-new-at-zerodha-march-2024

[^17]: https://kite.trade/docs/connect/v3/orders/

[^18]: https://support.zerodha.com/category/trading-and-markets/general-kite/others-kite/articles/order-types-and-execution

[^19]: https://zerodha.com/z-connect/featured/order-placement-simplified

[^20]: https://kite.trade/forum/discussion/11886/iceberg-order-type

[^21]: https://tradingqna.com/t/kite-api-historical-data-retreival-limit/177114

[^22]: https://zerodha.com/z-connect/kite/introducing-iceberg-orders-and-order-validity-in-minutes

[^23]: https://kite.trade/docs/pykiteconnect/v4/

[^24]: https://www.youtube.com/watch?v=gHuuvaqdAvY

[^25]: https://github.com/Niteshkpatel/Kite-API-Mod

[^26]: https://www.combiz.org/blogs/how-to-set-up-algo-trading-in-zerodha-using-kite-api

[^27]: https://kite.trade/docs/connect/v3/sdks/

[^28]: https://www.profitaddaweb.com/2017/

[^29]: https://github.com/Cranial490/QuantWorks

[^30]: https://kite.trade/docs/connect/v3/gtt/

[^31]: https://support.zerodha.com/category/trading-and-markets/charts-and-orders/gtt/articles/how-can-i-use-the-gtt-feature

[^32]: https://support.zerodha.com/category/trading-and-markets/charts-and-orders/gtt/articles/what-is-the-good-till-triggered-gtt-feature

[^33]: https://zerodha.com/z-connect/kite/introducing-gtt-good-till-triggered-orders

[^34]: https://support.zerodha.com/category/trading-and-markets/kite-features/gtt/articles/how-to-modify-gtt

[^35]: https://support.zerodha.com/category/trading-and-markets/general-kite/kite-api/articles/what-are-the-charges-for-kite-apis

[^36]: https://github.com/QuickLearner171998/Python-Algo-Trading-Zerodha

[^37]: https://support.zerodha.com/category/trading-and-markets/trading-faqs/articles/why-bo-stopped

[^38]: https://kite.trade/docs/connect/v3/exceptions/

[^39]: https://kite.trade/forum/discussion/8577/api-rate-limits

[^40]: https://support.zerodha.com/category/trading-and-markets/alerts-and-nudges/kite-error-messages/articles/order-rate-limits-on-kite

[^41]: https://zerodha.com/products/api/

[^42]: https://www.chittorgarh.com/broker/zerodha/api-for-algo-trading-review/18

[^43]: https://community.auth0.com/t/change-expiration-time-of-access-token/125726

[^44]: https://support.zerodha.com/category/trading-and-markets/general-kite/kite-api/articles/why-am-i-getting-the-error-maximum-allowed-order-request-exceeded

[^45]: https://kite.trade/forum/discussion/7759/access-token-validity

[^46]: https://zerodha.com/z-connect/updates/free-personal-apis-from-kite-connect

[^47]: https://kite.trade/forum/discussions

[^48]: https://github.com/zerodha/pykiteconnect/blob/master/kiteconnect/connect.py

[^49]: https://kite.trade/forum/discussion/13943/faqs-on-pykiteconnect-specific-to-python-client

[^50]: https://kite.trade/forum/discussion/11726/gtt-order-directly

