import os
from dotenv import load_dotenv

def test_anthropic_setup():
    """Test Anthropic API setup"""
    print("🧪 Testing Anthropic API Setup")
    print("=" * 50)
    
    # Load environment
    load_dotenv()
    
    try:
        import anthropic
        print(f"✅ Anthropic library version: {anthropic.__version__}")
    except ImportError:
        print("❌ Anthropic library not installed")
        print("   Run: pip install anthropic")
        return False
    except AttributeError:
        print("✅ Anthropic library installed (version unknown)")
    
    # Check API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ No ANTHROPIC_API_KEY found in environment")
        print("   Add to .env file: ANTHROPIC_API_KEY=your-key-here")
        return False
    
    if api_key.startswith("sk-ant-"):
        print("✅ API key format looks correct")
    else:
        print("⚠️  API key format seems unusual (should start with 'sk-ant-')")
    
    # Test client initialization
    try:
        client = anthropic.Anthropic(api_key=api_key)
        print("✅ Anthropic client created successfully")
        
        # Test a simple API call
        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}]
            )
            print("✅ API call successful")
            return True
        except Exception as e:
            print(f"❌ API call failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Client initialization failed: {e}")
        return False

if __name__ == "__main__":
    test_anthropic_setup()
