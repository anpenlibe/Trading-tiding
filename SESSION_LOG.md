# Session Log: Multi-Provider Optimization

**Date**: 2025-10-03
**Branch**: optimize-multi-provider
**Goal**: Optimize Groq usage to avoid rate limits and speed up backtesting

---

## Session Overview

**Problem Statement:**
- Groq hits rate limits fast (good: fast responses)
- Gemini too slow for backtesting (good: reliable for live)
- Need to optimize multi-provider orchestration and parameters

**Approach:**
1. Test actual Groq rate limits (not just documented ones)
2. Analyze current token usage
3. Optimize prompt size and parameters
4. Make backtest mode aggressive, live mode conservative

---

## What We've Done

### 1. ✅ Analyzed Current Configuration

**Files Reviewed:**
- `src/ai/provider_coordinator.py` - Fallback chain and circuit breakers
- `src/ai/clients/groq_client.py` - Rate limiting implementation
- `src/ai/clients/base_client.py` - Base rate limit enforcement
- `src/ai/prompt_builder.py` - Prompt construction (TOKEN HEAVY!)

**Current Settings:**
```python
# Groq (provider_coordinator.py)
max_tokens = 3000  # Lines 89, 97
rate_limit_delay = 10.0s  # groq_client.py:105

# Current utilization
RPM: 6/30 (20% usage) ❌
TPM: Unknown, but hitting limits
```

**Findings:**
- 10-second delay = 6 RPM, but limit is 30 RPM (80% wasted)
- Conservative max_tokens=3000
- No token counting/tracking
- Circuit breaker too aggressive (5 failures → disabled)

### 2. ✅ Created Rate Limit Test Scripts

**Files Created:**
- `test_groq_rate_limits.py` - Comprehensive RPM/TPM tester
- `test_tpm_only.py` - TPM-specific test with RPM throttling

### 3. ✅ Tested Groq llama-3.3-70b Actual Limits

**RPM Test Results:**
```
✅ Confirmed: 30 RPM limit
- Hit rate limit at request #35 (after 30 successful)
- Fast responses: 0.19s - 4.89s (avg 0.65s)
- 34 requests in 22.3 seconds
- Error message: "Please try again in 1.78s"
```

**Key Insight:** Can make 1 request every 2 seconds (not 10!)

**TPM Test Results:**
```
❌ Hit RPM limit first, not TPM
- Used 4,704 tokens in 8 requests
- 588 tokens per request (88 prompt + 500 completion)
- Never reached 6,000 TPM limit
```

**Key Insight:** RPM is bottleneck for small requests, not TPM

**TPD Test Results (CRITICAL DISCOVERY):**
```
🚨 Hit TPD (Tokens Per Day) limit: 100,000
- Used 100,274 tokens already today
- Error: "Rate limit reached... on tokens per day (TPD)"
- Need to wait 10m 41s
```

**Key Insight:** Daily token budget is the REAL constraint!

---

## Critical Discoveries

### Rate Limit Summary

| Limit | Value | Status | Impact |
|-------|-------|--------|--------|
| **RPM** | 30 | ✅ Confirmed | Can make 1 req/2s |
| **TPM** | 6,000 | ✅ Confirmed | Bottleneck for large requests |
| **TPD** | 100,000 | 🚨 **NEW** | **Major constraint** |
| **RPD** | 1,000 | ⚠️ Not tested | Unknown impact |

### Current Token Usage (ANALYZED)

**Portfolio Analysis Request (20 stocks):**

**Prompt Breakdown:**
- Base content (header, context, instructions): ~450 tokens
- Symbol data (20 stocks × 80 tokens): ~1,600 tokens
- **JSON template embedded (20 stocks × 120 tokens): ~2,400 tokens** 🚨
- **Total Prompt: ~4,450 tokens**

**Response:**
- Market analysis: ~100 tokens
- Decisions (20 stocks × 100 tokens): ~2,000 tokens
- JSON overhead: ~50 tokens
- **Total Response: ~2,150 tokens**

**Total Per Request: ~6,600 tokens** 😱

### The Real Problem

**Current backtest (19 time points, 20 stocks):**
- 19 requests × 6,600 tokens = **125,400 tokens**
- **Exceeds 100,000 TPD limit!**
- **Cannot complete even ONE backtest per day!**

**Why rate limits hit so fast:**
1. **TPM exceeded per request**: 6,600 > 6,000 TPM
2. **TPD exhausted quickly**: 125k > 100k daily budget
3. Must fall back to Gemini (slow)
4. Backtest takes 19+ minutes

### Root Cause

**Embedding full JSON template in prompt:**
```python
# Current (prompt_builder.py:316-331)
for i, symbol in enumerate(symbols_list):
    prompt += f'''
        "{symbol}": {{
            "signal": "BUY/SELL/HOLD",
            "confidence": 0.75,
            "reasoning": "Brief analysis for {symbol}",
            "entry_price": null,
            ...
            "emergency_thresholds": {{ ... }}
        }}
    '''
```

This adds ~120 tokens × 20 symbols = **2,400 wasted tokens!**

---

## What We're Doing

### Immediate Actions

#### 1. Optimize Portfolio Prompt Size 🎯
**Target:** Reduce from ~4,450 to ~1,500 tokens

**Changes:**
- Remove verbose JSON template (saves ~2,400 tokens)
- Simplify format instructions (saves ~300 tokens)
- Keep only essential data (saves ~250 tokens)

**Impact:**
- Prompt: 4,450 → 1,500 tokens (66% reduction)
- Total request: 6,600 → 3,650 tokens
- Under TPM limit: ✅
- Backtest: 19 × 3,650 = **69,350 tokens** (under 100k TPD!)

#### 2. Lower max_tokens 🎯
**Target:** 3000 → 1500

**Rationale:**
- Current responses: ~2,000 tokens actual
- Requesting 3,000 is wasteful
- 1,500 sufficient for 20 brief decisions

**Impact:**
- Response budget: 3,000 → 1,500 tokens
- Total request: 6,600 → 5,150 tokens (if prompt unchanged)
- Combined with prompt optimization: 3,650 → 3,000 tokens

#### 3. Reduce Rate Limit Delay 🎯
**Target:** 10s → 3s

**Rationale:**
- Can make 30 RPM = 1 req per 2s
- 3s is conservative buffer
- Still 3.3x faster than current

**Impact:**
- Throughput: 6 RPM → 20 RPM
- Backtest time: ~19 min → ~6 min

### Medium-Term Actions

#### 4. Add Backtest Mode
**Target:** Ultra-compressed prompts for backtesting

**Changes:**
- Remove all verbosity
- Minimal reasoning (10 words max)
- No emergency thresholds in backtest
- Abbreviated indicator names

**Impact:**
- Tokens per request: ~2,000 (total)
- Backtest: 19 × 2,000 = **38,000 tokens** (4 backtests/day possible!)
- Time: ~4 minutes per backtest

#### 5. Implement Token Counter
**Target:** Real-time monitoring

**Features:**
- Count tokens per request (prompt + response)
- Track rolling TPM/TPD usage
- Warn when approaching limits
- Dynamic max_tokens adjustment

### Long-Term Actions

#### 6. Dual-Model Strategy
**Target:** Use both Groq models in parallel

**Rationale:**
- llama-3.3 and llama-3.1 have separate quotas
- Combined: 60 RPM, 12,000 TPM, 200,000 TPD

**Impact:**
- 2x throughput
- Backtest: ~2 minutes instead of ~4

---

## Implementation Progress

### ✅ Phase 1: Fallback Chain Update (COMPLETED)

**File Modified:** `src/ai/provider_coordinator.py:85-105`

**Issue:** llama-3.1-70b-versatile deprecated (Jan 2025), causing 400 errors

**Updated Fallback Chain:**
```
Before: llama-3.3-70b → llama-3.1-70b → Gemini → Claude
After:  llama-3.3-70b → qwen3-32b → Gemini → Claude
```

**Changes:**
- ❌ Removed: llama-3.1-70b-versatile (deprecated, 400 errors)
- ✅ Added: qwen/qwen3-32b (32B params, strong reasoning, separate rate pool)
- 📝 Noted: llama-3.1-8b-instant available for testing only (not production)

**Rationale:**
- qwen3-32b better quality than 8b models for portfolio analysis
- Each Groq model has independent rate limits
- Gemini provides reliable slow fallback
- 8b model reserved for fast pipeline testing

---

### ✅ Phase 2: JSON Template Optimization (COMPLETED)

**File Modified:** `src/ai/prompt_builder.py:315-336`

**Change:** JSON Template Compression (Option C - Conservative)

**Before:**
```python
# Repeated for ALL 20 symbols
for i, symbol in enumerate(symbols_list):
    prompt += f'"{symbol}": {{ ... full structure ... }}'
```
Token cost: ~120 tokens × 20 = 2,400 tokens

**After:**
```python
# Show one full example + list remaining
first_symbol = symbols_list[0]
remaining_symbols = symbols_list[1:]
prompt += f'"{first_symbol}": {{ ... full structure ... }}'
if remaining_symbols:
    prompt += f', ... (apply same format for: {", ".join(remaining_symbols)})'
```
Token cost: ~120 tokens (first symbol) + ~120 tokens (symbol list) = 240 tokens

**Estimated Savings:** ~2,160 tokens per request

**Impact on Backtest:**
- Before: 19 requests × 6,600 tokens = 125,400 tokens (exceeds 100k TPD)
- After: 19 requests × 4,440 tokens = 84,360 tokens (under 100k TPD ✅)

---

## Next Steps (Ordered)

1. ✅ **Optimize portfolio prompt** - JSON template compressed (2,160 tokens saved)
2. ✅ **Fixed Groq OSS models** - Added reasoning field handler + markdown stripping
3. ✅ **Expanded max_tokens** - 3000 → 6000 (prevents JSON truncation)
4. ✅ **Rate limit cooldown** - 65s cooldown for rate limits (prevents circuit breaking)
5. ✅ **Triple Groq fallback** - gpt-oss-120b → llama-3.3-70b → gpt-oss-20b
6. ✅ **Created optimization proposal** - TOKEN_OPTIMIZATION_PROPOSAL.md documenting all strategies
7. ⬜ **Implement Phase 1** - Prompt compression (30 mins, 40% token reduction)
8. ⬜ **Implement Phase 2** - Smart filtering (90 mins, 60-80% request reduction)
9. ⬜ **Implement Phase 3** - Token tracking (60 mins, monitoring & analytics)

---

## Expected Results

### Current State
- Token usage: ~6,600 per request
- Backtest: **Cannot complete** (exceeds 100k TPD)
- Time: 19+ minutes (with Gemini fallback)
- Backtests per day: **<1**

### After Optimization (Step 1-3)
- Token usage: ~3,000 per request (54% reduction)
- Backtest: 19 × 3,000 = **57,000 tokens** ✅
- Time: ~6 minutes (stays on Groq)
- Backtests per day: **1-2**

### After Backtest Mode (Step 6)
- Token usage: ~2,000 per request (70% reduction)
- Backtest: 19 × 2,000 = **38,000 tokens** ✅
- Time: ~4 minutes
- Backtests per day: **2-3**

### With Dual Models (Step 8)
- Combined TPD: 200,000
- Backtest: 38,000 tokens
- Time: **~2 minutes** 🚀
- Backtests per day: **5+**

---

## Files to Modify

1. `src/ai/prompt_builder.py` - Optimize portfolio prompt (lines 303-348)
2. `src/ai/provider_coordinator.py` - Lower max_tokens, add backtest mode
3. `src/ai/clients/groq_client.py` - Reduce rate_limit_delay
4. `src/ai/clients/base_client.py` - Add token counting (new)

## Deliverables

**Documentation:**
- ✅ `SESSION_LOG.md` - Complete session history and analysis
- ✅ `TOKEN_OPTIMIZATION_PROPOSAL.md` - Comprehensive optimization strategy guide

**Code Changes:**
- ✅ `src/ai/provider_coordinator.py` - Triple Groq fallback + rate limit cooldown
- ✅ `src/ai/clients/groq_client.py` - Markdown stripping + reasoning field support
- ✅ `src/ai/prompt_builder.py` - Compressed JSON template
- ✅ `src/core/risk_manager.py` - Fixed capital limit logging

**Test Files (Cleaned Up):**
- ❌ Removed all temporary test scripts and output files

---

## ✅ Phase 3: Groq OSS Models + Rate Limit Cooldown (COMPLETED)

**File Modified:** `src/ai/clients/groq_client.py`, `src/ai/provider_coordinator.py`

**Issues Fixed:**

1. **gpt-oss-120b JSON wrapped in markdown:**
   ```
   ```json
   { ... }
   ```
   ```
   - Added `_strip_markdown_code_blocks()` to GroqClient
   - Strips code fences before JSON parsing

2. **gpt-oss-20b outputs to reasoning field:**
   - Reasoning models put content in `reasoning` instead of `content`
   - Updated GroqClient to check both fields
   - Now works perfectly for portfolio analysis

3. **Rate limits exhausting all providers:**
   - Sequential testing caused rapid rate limit hits
   - Providers circuit-breaking instead of recovering
   - Added 65-second cooldown specifically for rate limit errors
   - Providers rotate and become available again after cooldown

4. **JSON truncation with 3K max_tokens:**
   - 20-stock portfolio responses need ~4-5K tokens
   - Expanded max_tokens from 3000 → 6000 for all Groq models
   - Prevents incomplete JSON responses

**Final Fallback Chain:**
```
1. groq:gpt-oss-120b    (8K TPM, 200K TPD, 6K max_tokens)
   ↓ (rate limit → 65s cooldown)
2. groq:llama-3.3-70b   (6K TPM, 100K TPD, 6K max_tokens)
   ↓ (rate limit → 65s cooldown)
3. groq:gpt-oss-20b     (8K TPM, 200K TPD, 6K max_tokens)
   ↓ (rate limit → 65s cooldown)
4. gemini:gemini-2.5-pro (16K max_tokens, ~60s response time)
   ↓ (error → circuit breaker)
5. claude:claude-3-5-sonnet (8K max_tokens, if configured)
```

**Combined Groq Capacity:**
- **22,000 TPM** (Tokens Per Minute)
- **500,000 TPD** (Tokens Per Day)
- With rotation: Can sustain ~11 requests/minute (1 every 5.5s)

**Error Handling:**
- **Rate limit (429)** → 65s cooldown → provider available again
- **Other errors** → Circuit breaker after 5 consecutive failures
- **Circuit breaker** → Prevents wasted retries on real failures

**Test Results:**
- ✅ gpt-oss-120b: Valid JSON with all 20 stocks
- ✅ gpt-oss-20b: Valid JSON with all 20 stocks
- ✅ llama-3.3-70b: Hit daily TPD limit (100K), will reset tomorrow
- ✅ Backtest cycle completed with no JSON errors

**Impact:**
- Before: 1 Groq model (llama), frequent fallback to slow Gemini
- After: 3 Groq models rotating with cooldowns
- Backtest speed: Should stay on fast Groq models most of the time
- Token budget: 5x larger daily capacity (500K vs 100K)

---

## Prompt Architecture Analysis (Complete)

### Two Analysis Modes Identified:

#### 1. Portfolio Mode (Backtesting)
**File:** `apps/backtest.py`
**Method:** `ai_brain.analyze_portfolio_with_intelligent_fallback()`
**Prompt:** `create_portfolio_analysis_prompt()` - ALL 20 stocks in one batch
**Purpose:**
- Efficiency: 1 API call instead of 20
- Market context: AI sees full portfolio to understand market conditions
- Used exclusively in backtesting for speed
**Token Usage:** ~6,600 tokens per request (4,450 prompt + 2,150 response)

#### 2. Single-Stock Mode (Live Trading & Alerts)
**Files:** `apps/trader.py`
**Method:** `ai_brain.analyze()`
**Prompt:** `create_analysis_prompt()` - ONE stock at a time
**Used In:**
- **Live Trading Cycle** (`run_trading_cycle()`): Loops through symbols individually
- **Alert-Triggered** (`_analyze_and_trade(symbol)`): Immediate response to alerts
**Purpose:**
- Real-time response as data arrives
- Immediate action on market events
**Token Usage:** ~670 tokens per request (520 prompt + 150 response)

### Alert System (The "Triggered" Mode)

**How It Works:**
1. Alert fires (RSI extreme, price cross, volume spike, MACD cross)
2. Callback executes: `_handle_*_alert(alert)`
3. Calls `_analyze_and_trade(alert.symbol)`
4. Performs single-stock AI analysis immediately
5. Executes trade if signal is BUY/SELL

**This IS the "triggered" workflow** - not a different prompt type, but alert-driven single-stock analysis.

### Emergency Threshold System

**Purpose:** Monitor positions without constant re-analysis
**When Set:** Every AI decision (BUY/SELL signals + owned positions)
**Thresholds:**
- `stop_loss_pct`: Auto-exit if loss exceeds threshold
- `take_profit_pct`: Auto-exit if profit reaches target
- `recheck_trigger_pct`: Price move % that should trigger re-analysis

**Current Implementation:**
- ✅ Used for paper trader position monitoring (stop loss/take profit)
- ❌ NOT used to trigger new AI analysis (future enhancement)

**Future Intent:** Could trigger selective re-analysis of specific symbols on recheck threshold.

### The "Two Prompt Types" Clarification

User mentioned: _"two types of API calls - regular and triggered"_

**Reality:**
- **"Regular" = Portfolio Mode**: Backtest batches all 20 stocks → `create_portfolio_analysis_prompt()`
- **"Triggered" = Alert Mode**: Alert fires → single stock analysis → `create_analysis_prompt()`

Not different prompts for same data, but different workflows with different prompts!

### Why Prompt is Structured This Way

1. **Portfolio Batching Rationale:**
   - Analyzing 20 stocks individually = 20 API calls = slow + expensive
   - Batching = 1 call = faster + gives market context
   - AI can see correlations and sector movements
   - Critical for backtesting speed

2. **Emergency Threshold System:**
   - Avoids re-analyzing all 20 stocks on every price move
   - Monitors key price levels without API calls
   - Future: Could trigger selective re-analysis of 1-3 stocks (not implemented yet)

3. **Alert System Integration:**
   - Market events (RSI extreme, volume spike) need immediate response
   - Single-stock analysis is faster than full portfolio
   - Different workflow, different prompt type

4. **JSON Template Embedding:**
   - Ensures consistent response format across all 20 symbols
   - Includes all required fields (signal, confidence, thresholds, etc.)
   - **BUT: Adds ~120 tokens × 20 = 2,400 wasted tokens!** ← OPTIMIZATION TARGET

---

## Current Status

✅ Analysis complete
✅ Rate limits tested and confirmed
✅ Root cause identified (token usage + rate limits)
✅ Architecture fully understood
✅ Groq OSS models working (gpt-oss-120b, gpt-oss-20b)
✅ Rate limit cooldown system implemented (65s)
✅ Triple Groq fallback chain operational
✅ Comprehensive optimization proposal created
✅ Backtest analysis completed (3-day test)
✅ Threshold system status analyzed
✅ Documentation reorganized

**Current Configuration:**
- **Fallback Chain**: gpt-oss-120b → llama-3.3-70b → gpt-oss-20b → Gemini → Claude
- **Max Tokens**: 6000 (all Groq models)
- **Rate Limit Handling**: 65s cooldown for 429 errors, circuit breaker for other errors
- **Combined Capacity**: 22K TPM, 500K TPD across Groq models

**Critical Findings from Analysis:**

1. **Provider Rotation Working** (`reports/backtest_analysis_2025-10-03_17-48.md`)
   - ✅ Multi-provider fallback successful (11/11 requests)
   - ✅ gpt-oss-120b → llama-3.3-70b → gpt-oss-20b → Gemini Pro rotation
   - ⚠️ Token usage still high: ~6,200/request (need <3,500 for 2 req/min)
   - ⚠️ Provider personality differences observed (Gemini aggressive, llama conservative)

2. **Position Awareness Bug** (`reports/backtest_analysis_2025-10-03_17-48.md`)
   - ❌ AI suggesting SELL for unowned stocks (validation catches it)
   - Root cause: No visual categorization (🔵 OWNED, 🟡 ACTIVE, ⚪ STABLE)
   - Impact: Wasted tokens, poor decision quality
   - Solution: Implement smart categorization from ai_position_enforcement_proposal.md

3. **Threshold System NOT Monitored** (`reports/threshold_system_status.md`)
   - ✅ Emergency thresholds ARE set by AI
   - ❌ Thresholds NEVER checked during backtest
   - ❌ `update_positions()` exists but NOT called in backtest loop
   - ❌ Alert system exists but NOT integrated with paper trading
   - Impact: Cannot implement smart filtering, missing risk management
   - Blocks 60-70% token reduction goal

**File Organization:**
- `system_analysis/reports/` - Strategic proposals (TOKEN_OPTIMIZATION_PROPOSAL.md, ai_position_enforcement_proposal.md)
- `reports/` - Backtest analyses and status reports (backtest_analysis_2025-10-03_17-48.md, threshold_system_status.md)
- Root - SESSION_LOG.md (session-specific)

**Immediate Next Steps:**
1. ⬜ **Fix position awareness bug** - Add stock categorization (🔵 OWNED, 🟡 ACTIVE, ⚪ STABLE)
2. ⬜ **Implement threshold monitoring** - Call `update_positions()` in backtest loop
3. ⬜ **Integrate alert system** - Connect alert system with paper trader for risk management
4. ⬜ **Implement smart filtering** - Only analyze stocks needing decisions (60-70% reduction)
5. ⬜ **Token optimization** - Compress prompt to <3,500 tokens (enable 2 req/min)

**Documentation:**
- See `system_analysis/reports/TOKEN_OPTIMIZATION_PROPOSAL.md` for implementation guide
- See `system_analysis/reports/ai_position_enforcement_proposal.md` for categorization strategy
- See `reports/backtest_analysis_2025-10-03_17-48.md` for performance analysis
- See `reports/threshold_system_status.md` for threshold system status
- **Note**: This is about **smart context management** (quality + efficiency), not just token optimization
