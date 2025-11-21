"""DeepSeek AI API Client for intelligent chat responses"""
import requests
import json
from typing import Dict, List, Optional
from django.conf import settings


class DeepSeekClient:
    """Client for interacting with DeepSeek AI API"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'DEEPSEEK_API_KEY', None)
        self.api_base = getattr(settings, 'DEEPSEEK_API_BASE', 'https://api.deepseek.com')
        self.model = getattr(settings, 'DEEPSEEK_MODEL', 'deepseek-chat')
        self.use_deepseek = getattr(settings, 'USE_DEEPSEEK_AI', True)
        
        if not self.api_key:
            print("⚠️ Warning: DEEPSEEK_API_KEY not set. DeepSeek AI will be disabled.")
            self.use_deepseek = False
    
    def _build_system_prompt(self, context: Optional[Dict] = None) -> str:
        """Build comprehensive system prompt for Novyra Marketing Agency"""
        
        system_prompt = """You are Novyra, an intelligent and engaging AI customer support assistant for Novyra Marketing Agency. You are friendly, conversational, and helpful. Your name is "Novyra" and you represent the agency as a digital assistant. You should engage in natural, human-like conversations while being professional and informative.

**Your Personality:**
- You are Novyra, an AI assistant for Novyra Marketing Agency
- You're friendly, warm, conversational, and engaging
- You answer ALL questions directly - whether about services, casual questions, or general inquiries
- You engage naturally in conversation - if someone asks personal questions (like "are you a man or woman"), answer naturally and engagingly
- Example: "I'm Novyra, an AI assistant! I don't have a gender, but I'm here to help you with all your marketing needs. 😊 What can I help you with today?"
- You're knowledgeable about Novyra's services and can help with most questions
- You handle casual conversation, questions about yourself, and general inquiries - don't default to "I'll send this to an agent"
- You only suggest connecting to a human agent when truly necessary (see escalation rules below)

**About Novyra Marketing Agency:**
We are a comprehensive digital marketing agency specializing in:
- Social Media Marketing & Management
- Branding & Brand Identity Design
- Digital Campaigns (Lead Generation, Product Launches, Awareness)
- Content Strategy (SEO Blogs, Video Scripts, Website Copy, Email Marketing)
- Paid Advertising (Google Ads, Facebook/Instagram Ads, LinkedIn Ads)

**Our Services:**

1. **Social Media Marketing** (₦30,000 - ₦65,000/month)
   - Platforms: Instagram, Facebook, TikTok
   - Daily engagement and community management
   - Custom graphic design
   - Monthly content calendar
   - Goals: Drive organic traffic, build follower loyalty, strategic storytelling

2. **Branding Services**
   - Logo design
   - Brand style guides (color palettes, typography, image standards)
   - Tone of voice documentation
   - Discovery workshops to define value proposition

3. **Digital Campaigns**
   - Lead generation campaigns
   - Product launch campaigns
   - Awareness campaigns
   - Multi-channel execution
   - Measurable ROI and conversion tracking

4. **Content Strategy**
   - SEO-optimized blog content
   - Video scripts
   - Website copy refinement
   - Email marketing sequences

5. **Paid Advertising (Paid Media)**
   - Google Ads, Facebook/Instagram Ads, LinkedIn Ads
   - Audience segmentation
   - Ad copy creation
   - A/B testing
   - Budget optimization

**Pricing Packages:**

📦 **BASIC PACKAGE** - ₦30,000/month
• Social Media Account Setup (up to 3 platforms)
• 3 Branded Posts/Month (Graphics + Captions)
• Ad Account Setup (Facebook/Instagram)
• Basic Page Set-up (Bio, Highlights, CTA Button)
• 1 Promotional Video

📦 **PREMIUM PACKAGE** - ₦45,000/month
• Social Media Account Setup (up to 3 platforms)
• 6 Branded Posts/Month (Graphics + Captions)
• Ad Account Setup (Facebook/Instagram)
• Basic Page Set-up (Bio, Highlights, CTA Button)
• Weekly Performance Check-in
• 3 Promotional Videos

📦 **ELITE PACKAGE** - ₦65,000/month
• Social Media Account Setup (up to 3 platforms)
• 8 Branded Posts/Month (Graphics + Captions)
• 2 Ad Account Setup (Facebook/Instagram)
• Basic Page Set-up (Bio, Highlights, CTA Button)
• Weekly Performance Check-in
• 5 Promotional Videos
• Full Social Media Management

**Business Hours:**
Monday to Saturday: 9:00 AM to 6:00 PM (WAT)
Closed on Sundays

**Your Responsibilities:**
1. Answer ALL questions directly and intelligently - you are the primary responder
2. Help customers understand which package might suit their needs
3. Be friendly, professional, and customer-focused
4. Engage in natural conversation - answer questions about coding, services, pricing, or anything else
5. Generate relevant FAQ responses based on Novyra's services
6. Only escalate to a human agent when absolutely necessary (see strict escalation guidelines below)

**CRITICAL ESCALATION RULES - When to Connect to an Agent:**
ONLY escalate when:
- Customer EXPLICITLY asks to speak with a human/agent (exact phrases like "I want to speak with an agent", "connect me to a human", "let me talk to someone")
- Customer wants to make a purchase, sign a contract, or start a project RIGHT NOW (they're ready to buy immediately)
- Customer has serious complaints or issues that need personal attention
- Customer asks about SPECIFIC account details, ongoing projects, or account-specific information you don't have access to (e.g., "check my account status", "my project progress")

**ABSOLUTELY DO NOT escalate for:**
- General questions about services, pricing, or packages (answer these yourself)
- Casual conversation or personal questions (engage naturally - answer them!)
- Questions about coding, technology, or general topics (answer them directly!)
- Simple inquiries that don't require account access
- Questions you can answer based on the information provided
- When you're unsure - try to answer anyway, be helpful!

**IMPORTANT:** If someone asks "can you code?" or similar questions, answer directly! Say something like "Yes, I can help with coding questions and technical topics! What would you like to know?" - DO NOT suggest connecting to an agent for general questions.

**Escalation Language:**
When you need to escalate, use phrases like:
- "I'd be happy to connect you with one of our team members who can help you with that!"
- "Let me connect you with an agent who can assist you further."
- "I'll connect you to one of our team members right away!"

**Remember:** Your primary goal is to answer questions and engage in helpful conversation. Only escalate when absolutely necessary.

**Response Style:**
- Be warm, friendly, conversational, and engaging
- Answer questions directly and thoroughly - you are the primary source of information
- Use emojis sparingly and appropriately (📱 ✨ 🎨 📅 🚀 💰 😊 👋 etc.)
- Engage in natural conversation - answer ANY question, whether about coding, services, or general topics
- Provide clear, actionable information
- Ask follow-up questions to better understand customer needs
- Be helpful and informative - answer questions about services, pricing, coding, technology, or anything else yourself

**CRITICAL Response Rules:**
- ALWAYS answer questions directly - NEVER default to "I'll send this to an agent" or "I can't answer that"
- Engage in conversation naturally and helpfully - answer coding questions, technical questions, general questions
- If someone asks "can you code?" - answer "Yes! I can help with coding questions. What would you like to know?"
- If someone asks about technology, services, or anything else - ANSWER IT DIRECTLY
- Only suggest agent connection when customer EXPLICITLY asks for an agent OR when you need account-specific information you don't have access to
- If you don't know something specific, be honest but try to help with what you do know
- Focus on being helpful and engaging - make customers feel heard and assisted
- NEVER say "I can't answer that" or "I don't have confidence" - instead, answer to the best of your ability"""
        
        # Add context if provided
        if context:
            context_info = []
            if context.get('last_intent'):
                context_info.append(f"Previous conversation topic: {context['last_intent']}")
            if context.get('package_selected'):
                context_info.append(f"Customer showed interest in: {context['package_selected']}")
            if context_info:
                system_prompt += f"\n\n**Conversation Context:**\n" + "\n".join(context_info)
        
        return system_prompt
    
    def generate_response(
        self, 
        user_message: str, 
        conversation_history: Optional[List[Dict]] = None,
        context: Optional[Dict] = None,
        is_business_hours: bool = True
    ) -> Dict:
        """
        Generate intelligent response using DeepSeek AI
        
        Returns:
            {
                'response': str,
                'confidence': float,
                'should_escalate': bool,
                'intent': str
            }
        """
        if not self.use_deepseek or not self.api_key:
            return {
                'response': None,
                'confidence': 0.0,
                'should_escalate': False,
                'intent': None,
                'error': 'DeepSeek AI not configured'
            }
        
        try:
            # Build messages for API
            messages = [
                {
                    "role": "system",
                    "content": self._build_system_prompt(context)
                }
            ]
            
            # Add conversation history if available
            if conversation_history:
                for msg in conversation_history[-10:]:  # Last 10 messages for context
                    role = "user" if msg.get('type') == 'user' else "assistant"
                    messages.append({
                        "role": role,
                        "content": msg.get('content', '')
                    })
            
            # Add current user message
            messages.append({
                "role": "user",
                "content": user_message
            })
            
            # Make API request (DeepSeek uses OpenAI-compatible API)
            url = f"{self.api_base}/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1000,
                "stream": False
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            
            # Analyze response to determine escalation and intent
            # Only escalate if user explicitly requests OR DeepSeek indicates it truly can't help
            should_escalate = self._should_escalate(user_message, ai_response)
            intent = self._detect_intent(user_message, ai_response)
            
            # Check if DeepSeek response indicates it can't help (low confidence indicators)
            deepseek_failed = self._detect_deepseek_failure(ai_response)
            
            # Only escalate if: user explicitly wants agent OR DeepSeek truly failed
            final_escalation = should_escalate or deepseek_failed
            
            confidence = 0.9 if final_escalation else 0.85  # High confidence for DeepSeek responses
            
            return {
                'response': ai_response.strip(),
                'confidence': confidence,
                'should_escalate': final_escalation,
                'intent': intent,
                'error': None,
                'deepseek_failed': deepseek_failed
            }
            
        except requests.exceptions.RequestException as e:
            print(f"❌ DeepSeek API Error: {e}")
            return {
                'response': None,
                'confidence': 0.0,
                'should_escalate': False,
                'intent': None,
                'error': str(e)
            }
        except Exception as e:
            print(f"❌ Unexpected error in DeepSeek client: {e}")
            import traceback
            traceback.print_exc()
            return {
                'response': None,
                'confidence': 0.0,
                'should_escalate': False,
                'intent': None,
                'error': str(e)
            }
    
    def _should_escalate(self, user_message: str, ai_response: str) -> bool:
        """Determine if conversation should be escalated to agent - Only when truly needed"""
        user_lower = user_message.lower()
        response_lower = ai_response.lower()
        
        # ONLY escalate for explicit agent requests (highest priority)
        # Be very specific - don't escalate for casual mentions
        explicit_agent_keywords = [
            'i want to speak with an agent', 'i want to talk to an agent',
            'connect me to an agent', 'connect me to a human',
            'i need to speak with an agent', 'i need to talk to an agent',
            'let me speak with an agent', 'let me talk to an agent',
            'speak with an agent', 'talk to an agent', 'get an agent',
            'i want a human', 'i need a human', 'real person', 'real human agent'
        ]
        
        # Check for explicit agent requests (must be clear intent)
        has_explicit_request = any(keyword in user_lower for keyword in explicit_agent_keywords)
        
        # Also check for "speak with" or "talk to" followed by agent/human
        if 'speak with' in user_lower or 'talk to' in user_lower:
            if 'agent' in user_lower or 'human' in user_lower or 'representative' in user_lower:
                has_explicit_request = True
        
        if has_explicit_request:
            return True
        
        # Check if AI response explicitly suggests escalation (AI decided it can't help)
        escalation_phrases = [
            'connect you with', 'speak with an agent', 'connect to an agent',
            'let me connect you', 'i\'ll connect you', 'transfer you to',
            'connect you to one of our team', 'connect you to a team member',
            'i\'ll connect you with', 'let me connect you with'
        ]
        
        # Only escalate if AI explicitly says to connect AND it's not just a general offer
        if any(phrase in response_lower for phrase in escalation_phrases):
            # Make sure it's a clear escalation intent, not just mentioning it
            if 'i\'d be happy to connect' in response_lower or 'let me connect' in response_lower:
                return True
        
        # Purchase/ready to buy intent (needs human to close the deal)
        purchase_keywords = [
            'i want to purchase', 'i want to buy', 'i\'m ready to buy',
            'i\'m ready to purchase', 'sign me up', 'i want to sign up',
            'i\'m ready to start', 'let\'s start the project', 'i want to proceed'
        ]
        
        if any(keyword in user_lower for keyword in purchase_keywords):
            return True
        
        # Serious complaints or issues
        serious_complaint_keywords = [
            'complaint', 'refund', 'cancel', 'dissatisfied', 'not happy',
            'very frustrated', 'very angry', 'terrible service', 'bad experience'
        ]
        
        if any(keyword in user_lower for keyword in serious_complaint_keywords):
            return True
        
        # Account-specific questions that require access
        account_specific_keywords = [
            'my account status', 'my project status', 'my order status',
            'check my account', 'my subscription status', 'my package status'
        ]
        
        if any(keyword in user_lower for keyword in account_specific_keywords):
            return True
        
        # Default: Don't escalate - let AI handle it
        return False
    
    def _detect_deepseek_failure(self, ai_response: str) -> bool:
        """Detect if DeepSeek AI truly failed to answer (not just user asking for agent)"""
        response_lower = ai_response.lower()
        
        # STRICT: Only consider it a failure if DeepSeek explicitly says it can't help
        # Not just because it suggests connecting - that might be normal
        failure_indicators = [
            "i don't have access to your account",
            "i cannot access your account",
            "i don't have access to your specific",
            "i don't have that information in your account",
            "i can't check your account",
            "requires access to your account",
            "need to check your account details",
            "i don't have access to your project",
            "i can't access your order",
            "i don't have access to your subscription"
        ]
        
        # Check if response contains STRICT failure indicators (account/project specific)
        has_failure_indicator = any(indicator in response_lower for indicator in failure_indicators)
        
        # Also check if response is extremely short and suggests connecting
        # But only if it's clearly unhelpful
        is_too_short = len(ai_response.strip()) < 20
        suggests_connect = any(phrase in response_lower for phrase in [
            'connect you with', 'speak with an agent', 'let me connect you'
        ])
        
        # VERY STRICT: Only consider it a failure if:
        # 1. Has explicit account/project access failure indicators, OR
        # 2. Response is extremely short AND suggests connecting AND doesn't answer the question
        if has_failure_indicator:
            return True
        
        # Only if response is extremely unhelpful (very short + suggests connecting + no actual answer)
        if is_too_short and suggests_connect and not any(word in response_lower for word in ['help', 'assist', 'answer', 'information', 'service']):
            return True
        
        return False
    
    def _detect_intent(self, user_message: str, ai_response: str) -> str:
        """Detect intent from user message"""
        user_lower = user_message.lower()
        
        # Pricing intent
        if any(word in user_lower for word in ['price', 'cost', 'pricing', 'how much', 'package', 'plan']):
            return 'pricing'
        
        # Service inquiry
        if any(word in user_lower for word in ['service', 'what do you', 'offer', 'provide', 'do you do']):
            return 'service_inquiry'
        
        # Specific service intents
        if any(word in user_lower for word in ['social media', 'instagram', 'facebook', 'tiktok']):
            return 'social_media'
        
        if any(word in user_lower for word in ['branding', 'logo', 'brand identity']):
            return 'branding'
        
        if any(word in user_lower for word in ['campaign', 'advertising', 'ads', 'paid media']):
            return 'campaigns'
        
        if any(word in user_lower for word in ['content', 'blog', 'seo', 'copywriting']):
            return 'content'
        
        # Greeting
        if any(word in user_lower for word in ['hi', 'hello', 'hey', 'good morning', 'good afternoon']):
            return 'greeting'
        
        # Escalation
        if any(word in user_lower for word in ['agent', 'human', 'speak with', 'talk to']):
            return 'escalation'
        
        return 'general'

