"""AI Core Engine - NLP and Intent Recognition with ML Learning"""
import re
import json
from typing import Dict, List, Tuple, Optional
from django.conf import settings
from .models import KnowledgeBase, ConversationLearning, WebsiteContent, ChatSession, Message
from .deepseek_client import DeepSeekClient


class AIEngine:
    """Core AI engine for intent recognition and response generation"""
    
    def __init__(self):
        self.confidence_threshold = getattr(settings, 'AI_CONFIDENCE_THRESHOLD', 0.7)
        self.escalation_keywords = getattr(settings, 'AI_ESCALATION_KEYWORDS', [])
        self.deepseek_client = DeepSeekClient()  # Initialize DeepSeek client
        
        # Abusive language patterns (common profanity and offensive terms)
        self.abusive_patterns = [
            r'\b(fuck|f\*\*k|f\*\*\*)\w*\b',
            r'\b(shut\s*up|shut\s*your|stupid|idiot|dumb|moron)\b',
            r'\b(asshole|bastard|bitch|damn|hell)\w*\b',
            r'\b(you\s*suck|you\s*are\s*stupid|you\s*are\s*dumb)\b',
            # Add more patterns as needed
        ]
        
        # Novyra Marketing Services Information
        self.novyra_services = {
            'social_media_marketing': {
                'keywords': ['social media', 'instagram', 'facebook', 'tiktok', 'social media marketing', 'posting', 'engagement', 'community management', 'content calendar', 'organic traffic', 'follower loyalty', 'storytelling'],
                'content': """Social Media Marketing at Novyra goes beyond simple posting. We provide comprehensive social media management across Instagram, Facebook, and TikTok, including:

📱 Platforms Covered: Instagram, Facebook, TikTok
✨ Daily Engagement: Active community management to build meaningful connections
🎨 Custom Graphic Design: Professionally designed visuals that align with your brand
📅 Monthly Content Calendar: Strategic content planning with your approval before posting
🚀 Goals: Driving organic traffic to your business, building measurable follower loyalty, and strategic storytelling

Our goal is to create a consistent, engaging online presence that drives real business results and builds a community around your brand.""",
            },
            'branding': {
                'keywords': ['branding', 'logo', 'brand identity', 'brand style', 'logo design', 'brand guide', 'tone of voice', 'discovery workshop', 'color palette', 'typography', 'value proposition'],
                'content': """Our Branding services focus on delivering tangible assets that define your brand:

🎨 Logo Design: Custom logos that capture your brand's essence and make a lasting impression
📋 Brand Style Guides: Comprehensive guides including:
   • Color palettes that reflect your brand personality
   • Typography standards for consistent communication
   • Image standards and photography guidelines
💬 Tone of Voice Documentation: Defining how your brand communicates across all channels
🔍 Discovery Workshop: We conduct workshops to define your brand's unique value proposition

We help you build a cohesive brand identity that sets you apart from the competition and resonates with your target audience.""",
            },
            'digital_campaigns': {
                'keywords': ['digital campaigns', 'campaign', 'lead generation', 'product launch', 'awareness campaign', 'conversion tracking', 'roi', 'multi-channel', 'analytics'],
                'content': """Our Digital Campaigns service covers planning and executing strategic campaigns:

🎯 Campaign Types:
   • Lead generation campaigns to grow your customer base
   • Product launch campaigns to create buzz and drive sales
   • Awareness campaigns to increase brand visibility
📱 Multi-Channel Execution: Campaigns across various digital platforms for maximum reach
📊 Measurable ROI: Focus on tracking and optimizing for maximum return on investment
🔍 Conversion Tracking: Detailed analytics to measure campaign effectiveness and optimize performance

We create campaigns that drive measurable results and help you achieve your business objectives with data-driven strategies.""",
            },
            'content_strategy': {
                'keywords': ['content strategy', 'blog', 'seo', 'video scripts', 'website copy', 'email marketing', 'content creation', 'email sequences', 'seo-optimized'],
                'content': """Our Content Strategy service creates high-value content assets that convert:

📝 SEO-Optimized Blog Content: Articles that rank in search engines and drive organic traffic
🎬 Video Scripts: Engaging scripts for your video content that capture attention
✍️ Website Copy Refinement: Optimized copy that converts visitors into customers
📧 Email Marketing Sequences: Automated email campaigns that nurture leads through the sales funnel

All our content is created with one goal: to convert readers into action and drive measurable business growth. We don't just create content—we create content that works.""",
            },
            'advertising': {
                'keywords': ['advertising', 'paid media', 'google ads', 'facebook ads', 'instagram ads', 'linkedin ads', 'ad campaign', 'audience segmentation', 'ab testing', 'budget optimization', 'ad copy'],
                'content': """Our Advertising (Paid Media) service manages your paid ad campaigns with precision:

📱 Platforms: Google Ads, Facebook/Instagram Ads, LinkedIn Ads
🎯 Audience Segmentation: Targeting the right audience for maximum impact and conversion
✍️ Ad Copy Creation: Compelling copy that converts viewers into customers
🧪 A/B Testing: Testing creatives and strategies to optimize performance continuously
💰 Budget Optimization: Continuous optimization to maximize efficiency and ROI

We ensure every ad spend delivers maximum value and drives measurable results. Our team handles everything from campaign setup to ongoing optimization, so you get the best return on your advertising investment.""",
            },
        }
        
        # Pricing Information with interactive packages
        self.pricing_info = {
            'keywords': ['pricing', 'price', 'cost', 'how much', 'packages', 'plans', 'basic', 'premium', 'elite'],
            'content': """Here are our social media management packages:

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

Which package interests you? I can provide more details or help you get started!""",
            'packages': [
                {'name': 'Basic', 'price': '₦30,000/month', 'id': 'basic'},
                {'name': 'Premium', 'price': '₦45,000/month', 'id': 'premium'},
                {'name': 'Elite', 'price': '₦65,000/month', 'id': 'elite'},
            ]
        }
        
        # Business Hours Information
        self.business_hours_info = {
            'keywords': ['hours', 'working hours', 'open', 'closed', 'when are you open', 'business hours', 'available'],
            'content': """Our Business Hours:
🕐 Monday to Saturday: 9:00 AM to 6:00 PM (WAT)
🚫 Closed on Sundays

We're here to help you during business hours. If you contact us outside these hours, our agents will reach out to you via email as soon as we're open. Feel free to leave your message anytime, and we'll get back to you!""",
        }
    
    def normalize_text(self, text: str) -> str:
        """Normalize input text for matching"""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        normalized = self.normalize_text(text)
        # Simple keyword extraction (can be enhanced with NLTK)
        words = normalized.split()
        # Filter out common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'is', 'are', 'was', 'were'}
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return keywords
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple keyword-based similarity (0.0 to 1.0)"""
        keywords1 = set(self.extract_keywords(text1))
        keywords2 = set(self.extract_keywords(text2))
        
        if not keywords1 or not keywords2:
            return 0.0
        
        intersection = keywords1.intersection(keywords2)
        union = keywords1.union(keywords2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def learn_from_past_conversations(self, message: str) -> Optional[Dict]:
        """Learn from past successful conversations"""
        normalized_msg = self.normalize_text(message)
        
        # Find similar past conversations that were helpful
        past_conversations = ConversationLearning.objects.filter(
            was_helpful=True,
            escalated=False
        ).order_by('-confidence', '-created_at')[:50]
        
        best_match = None
        best_similarity = 0.0
        
        for past in past_conversations:
            similarity = self.calculate_similarity(normalized_msg, self.normalize_text(past.user_message))
            if similarity > best_similarity and similarity > 0.6:
                best_similarity = similarity
                best_match = {
                    'response': past.ai_response,
                    'intent': past.intent_detected,
                    'confidence': past.confidence * similarity  # Weight by similarity
                }
        
        return best_match
    
    def detect_intent(self, message: str, session_context: Optional[Dict] = None) -> Tuple[Optional[str], float, Optional[Dict]]:
        """
        Detect intent from user message with ML learning and context awareness
        Enhanced with modern AI patterns (Grok, Gemini, Selar-style intelligence)
        Returns: (intent, confidence, kb_entry)
        """
        normalized_msg = self.normalize_text(message)
        
        # Context-aware intent detection (like modern AI assistants)
        # Check for follow-up questions based on context
        if session_context:
            last_intent = session_context.get('last_intent')
            # If user is following up on pricing, services, etc.
            if last_intent == 'pricing' and any(word in normalized_msg for word in ['choose', 'select', 'want', 'interested', 'go with', 'pick']):
                return ('package_selection', 0.95, {
                    'content': 'Great choice! Which package interests you? I can help you get started right away.',
                    'title': 'Package Selection',
                    'packages': self.pricing_info.get('packages', []),
                })
        
        # First, check learned patterns
        learned_response = self.learn_from_past_conversations(message)
        if learned_response and learned_response['confidence'] > 0.7:
            return (learned_response['intent'], learned_response['confidence'], {
                'content': learned_response['response'],
                'title': 'Learned Response',
            })
        
        # Enhanced pattern matching - like Grok/Gemini style understanding
        # Check for greetings and casual conversation
        greeting_patterns = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'greetings']
        if any(pattern in normalized_msg for pattern in greeting_patterns) and len(normalized_msg.split()) < 5:
            return ('greeting', 0.95, {
                'content': "Hello! 👋 I'm here to help you with Novyra Marketing services. What can I assist you with today?",
                'title': 'Greeting',
            })
        
        # Check for thank you / appreciation
        appreciation_patterns = ['thank', 'thanks', 'appreciate', 'grateful', 'helpful']
        if any(pattern in normalized_msg for pattern in appreciation_patterns):
            return ('appreciation', 0.9, {
                'content': "You're very welcome! 😊 I'm glad I could help. Is there anything else you'd like to know about our services?",
                'title': 'Appreciation',
            })
        
        # Enhanced understanding - like Grok/Gemini
        # Check for goodbye/farewell
        goodbye_patterns = ['bye', 'goodbye', 'see you', 'farewell', 'later', 'gotta go', 'have to go', 'talk later']
        if any(pattern in normalized_msg for pattern in goodbye_patterns):
            return ('goodbye', 0.95, {
                'content': "Goodbye! 👋 It was great helping you today. Feel free to come back anytime if you have more questions. Have a wonderful day!",
                'title': 'Goodbye',
            })
        
        # Check for pricing queries
        pricing_keywords = self.pricing_info['keywords']
        pricing_matches = sum(1 for kw in pricing_keywords if kw in normalized_msg)
        if pricing_matches > 0:
            return ('pricing', 0.9, {
                'content': self.pricing_info['content'],
                'title': 'Pricing Information',
                'packages': self.pricing_info.get('packages', []),
            })
        
        # Check for business hours queries
        hours_keywords = self.business_hours_info['keywords']
        hours_matches = sum(1 for kw in hours_keywords if kw in normalized_msg)
        if hours_matches > 0:
            return ('business_hours', 0.9, {
                'content': self.business_hours_info['content'],
                'title': 'Business Hours',
            })
        
        # Check for service queries
        for service_key, service_data in self.novyra_services.items():
            service_keywords = service_data['keywords']
            service_matches = sum(1 for kw in service_keywords if kw in normalized_msg)
            if service_matches > 0:
                confidence = min(service_matches / max(len(service_keywords), 1), 1.0)
                if confidence >= 0.5:  # Lower threshold for services
                    return (f'service_{service_key}', confidence, {
                        'content': service_data['content'],
                        'title': service_key.replace('_', ' ').title(),
                    })
        
        # Check for escalation keywords
        if any(keyword in normalized_msg for keyword in self.escalation_keywords):
            return ('escalation', 0.9, None)
        
        # Search knowledge base
        kb_entries = KnowledgeBase.objects.filter(is_active=True).order_by('-priority')
        best_match = None
        best_confidence = 0.0
        best_intent = None
        
        for entry in kb_entries:
            # Match against keywords
            entry_keywords = [k.strip().lower() for k in entry.keywords.split(',')]
            keyword_matches = sum(1 for kw in entry_keywords if kw in normalized_msg)
            
            if keyword_matches > 0:
                # Calculate confidence based on keyword matches
                confidence = min(keyword_matches / max(len(entry_keywords), 1), 1.0)
                
                # Boost confidence if intent matches
                if entry.intent and entry.intent.lower() in normalized_msg:
                    confidence = min(confidence + 0.2, 1.0)
                
                # Also check content similarity
                content_sim = self.calculate_similarity(normalized_msg, entry.content.lower())
                confidence = max(confidence, content_sim * 0.8)
                
                # Boost confidence if this pattern was successful before
                successful_patterns = ConversationLearning.objects.filter(
                    intent_detected=entry.intent or entry.category,
                    was_helpful=True
                ).count()
                if successful_patterns > 0:
                    confidence = min(confidence + 0.1, 1.0)
                
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = entry
                    best_intent = entry.intent or entry.category
        
        if best_confidence >= self.confidence_threshold:
            return (best_intent, best_confidence, {
                'id': best_match.id,
                'content': best_match.content,
                'title': best_match.title,
            })
        
        # Fallback: generic response with professional, customer-loving tone
        return ('general', 0.5, {
            'content': "Thank you for reaching out! I'm here to help you. Could you please provide a bit more detail about what you're looking for? I want to make sure I give you the best possible assistance.",
            'title': 'General Response',
        })
    
    def detect_abusive_language(self, message: str) -> bool:
        """Detect if message contains abusive language"""
        normalized = self.normalize_text(message)
        for pattern in self.abusive_patterns:
            if re.search(pattern, normalized, re.IGNORECASE):
                return True
        return False
    
    def search_website_content(self, query: str) -> Optional[Dict]:
        """Search website content for relevant information"""
        try:
            normalized_query = self.normalize_text(query)
            query_keywords = set(self.extract_keywords(query))
            
            # Search active website content
            website_contents = WebsiteContent.objects.filter(is_active=True)
            best_match = None
            best_score = 0.0
            
            for content in website_contents:
                # Calculate similarity with content
                content_normalized = self.normalize_text(content.content)
                content_keywords = set(self.extract_keywords(content.content))
                
                # Keyword overlap
                keyword_overlap = len(query_keywords.intersection(content_keywords))
                total_keywords = len(query_keywords.union(content_keywords))
                score = keyword_overlap / total_keywords if total_keywords > 0 else 0.0
                
                # Also check title similarity
                if content.title:
                    title_sim = self.calculate_similarity(normalized_query, self.normalize_text(content.title))
                    score = max(score, title_sim * 0.8)
                
                if score > best_score and score > 0.3:  # Minimum threshold
                    best_score = score
                    best_match = {
                        'content': content.content[:500] + '...' if len(content.content) > 500 else content.content,
                        'title': content.title or 'Website Information',
                        'url': content.url,
                        'confidence': min(best_score, 0.9)  # Cap at 0.9 for website content
                    }
            
            return best_match
        except Exception as e:
            print(f"Error searching website content: {e}")
            return None
    
    def _get_conversation_history(self, session_id: str, limit: int = 10) -> List[Dict]:
        """Get conversation history for context"""
        try:
            if not session_id:
                return []
            
            session = ChatSession.objects.filter(session_id=session_id).first()
            if not session:
                return []
            
            messages = Message.objects.filter(session=session).order_by('-created_at')[:limit]
            history = []
            
            for msg in reversed(messages):  # Reverse to get chronological order
                history.append({
                    'type': msg.message_type,
                    'content': msg.content,
                    'created_at': msg.created_at.isoformat() if msg.created_at else None
                })
            
            return history
        except Exception as e:
            print(f"Error getting conversation history: {e}")
            return []
    
    def generate_response(self, message: str, session_id: str = None, is_business_hours: bool = True, session_context: Optional[Dict] = None) -> Dict:
        """
        Generate AI response for user message using DeepSeek AI (primary) with fallback
        Returns: {
            'response': str,
            'confidence': float,
            'intent': str,
            'escalation_needed': bool,
            'kb_entry': dict
        }
        """
        # Check for abusive language first
        if self.detect_abusive_language(message):
            return {
                'response': "I understand you might be frustrated, and I'm here to help in a respectful way. Could you please rephrase your question so I can assist you better? I want to make sure I give you the best possible support.",
                'confidence': 0.5,
                'intent': 'abusive_language',
                'escalation_needed': False,
                'kb_entry': None,
            }
        
        # PRIMARY: Try DeepSeek AI first (if enabled)
        if self.deepseek_client.use_deepseek:
            try:
                # Get conversation history for context
                conversation_history = self._get_conversation_history(session_id) if session_id else []
                
                # Add business hours info to context
                enhanced_context = session_context or {}
                enhanced_context['is_business_hours'] = is_business_hours
                
                # Get DeepSeek response
                deepseek_result = self.deepseek_client.generate_response(
                    user_message=message,
                    conversation_history=conversation_history,
                    context=enhanced_context,
                    is_business_hours=is_business_hours
                )
                
                # If DeepSeek returned a valid response, use it
                if deepseek_result.get('response') and not deepseek_result.get('error'):
                    return {
                        'response': deepseek_result['response'],
                        'confidence': deepseek_result.get('confidence', 0.85),
                        'intent': deepseek_result.get('intent', 'general'),
                        'escalation_needed': deepseek_result.get('should_escalate', False),
                        'deepseek_failed': deepseek_result.get('deepseek_failed', False),
                        'kb_entry': None,  # DeepSeek handles this internally
                    }
                else:
                    print(f"⚠️ DeepSeek API returned error, falling back to rule-based: {deepseek_result.get('error')}")
            except Exception as e:
                print(f"⚠️ DeepSeek API error, falling back to rule-based: {e}")
                import traceback
                traceback.print_exc()
        
        # FALLBACK: Use rule-based intent detection (original logic)
        intent, confidence, kb_entry = self.detect_intent(message, session_context)
        
        # If no good match found, try searching website content
        if not kb_entry or confidence < self.confidence_threshold:
            website_match = self.search_website_content(message)
            if website_match and website_match['confidence'] > confidence:
                kb_entry = website_match
                confidence = website_match['confidence']
                intent = 'website_content'
        
        # Determine if escalation is needed
        escalation_needed = (
            confidence < self.confidence_threshold or
            intent == 'escalation' or
            any(keyword in self.normalize_text(message) for keyword in self.escalation_keywords)
        )
        
        # If we can't understand the question (low confidence or no good match), offer to connect to agent
        # Check if it's an explicit escalation request first
        if intent == 'escalation' or any(keyword in self.normalize_text(message) for keyword in self.escalation_keywords):
            response_text = "I understand you'd like to speak with an agent. Let me connect you to one of our team members who can provide you with more clarity and assistance."
        elif confidence < self.confidence_threshold:
            # Low confidence - AI doesn't understand the question
            response_text = "I'm sorry, I can't answer that question with complete confidence. Let me connect you to an agent to get more clarity and ensure you receive the best possible assistance."
        elif kb_entry:
            # We have a good match - provide the response
            response_text = kb_entry.get('content', '')
            # Add friendly closing if not present
            if response_text and not any(phrase in response_text.lower() for phrase in ['feel free', 'happy to help', 'glad to', 'pleasure', 'contact us']):
                response_text += "\n\nFeel free to ask if you need any clarification or have additional questions. I'm here to help!"
        else:
            # Fallback (shouldn't normally reach here, but just in case)
            response_text = "Thank you for your question! I'd be happy to help you with that. Could you provide a bit more detail so I can give you the most accurate and helpful response?"
        
        return {
            'response': response_text,
            'confidence': confidence,
            'intent': intent,
            'escalation_needed': escalation_needed,
            'kb_entry': kb_entry,
        }
    
    def should_escalate(self, message: str, confidence: float) -> bool:
        """Determine if chat should be escalated to human agent"""
        normalized = self.normalize_text(message)
        has_escalation_keyword = any(kw in normalized for kw in self.escalation_keywords)
        low_confidence = confidence < self.confidence_threshold
        
        return has_escalation_keyword or low_confidence

