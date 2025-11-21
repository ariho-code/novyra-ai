"""Utility functions for chat app"""
from datetime import datetime, time
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import F
import pytz
import requests
from bs4 import BeautifulSoup
from .models import Agent, BusinessHours, Ticket, ConversationLearning, Notification, ChatSession, WebsiteContent


def check_business_hours():
    """Check if current time is within business hours (WAT: 9am-6pm, Monday-Saturday)"""
    try:
        # Get current time in WAT (West Africa Time - UTC+1)
        wat_timezone = pytz.timezone('Africa/Lagos')  # Lagos is in WAT
        now_wat = timezone.now().astimezone(wat_timezone)
        current_day = now_wat.weekday()  # 0 = Monday, 6 = Sunday
        
        # Check if it's Sunday (day 6) - closed on Sundays
        if current_day == 6:  # Sunday
            return False
        
        # Check business hours: 9am to 6pm (Monday-Saturday)
        current_time = now_wat.time()
        open_time = time(9, 0)  # 9:00 AM
        close_time = time(18, 0)  # 6:00 PM
        
        # Check if within business hours
        is_within_hours = open_time <= current_time <= close_time
        
        # Also check if BusinessHours model has custom settings
        business_hours = BusinessHours.objects.filter(day_of_week=current_day).first()
        if business_hours:
            if not business_hours.is_open:
                return False
            # Use custom hours if set, otherwise use default 9am-6pm
            open_time = business_hours.open_time
            close_time = business_hours.close_time
            is_within_hours = open_time <= current_time <= close_time
        
        return is_within_hours
    except Exception as e:
        # Default to available if no business hours configured or error
        print(f"Error checking business hours: {e}")
        return True


def get_business_hours_message():
    """Get business hours message for display"""
    try:
        wat_timezone = pytz.timezone('Africa/Lagos')
        now_wat = timezone.now().astimezone(wat_timezone)
        current_day = now_wat.weekday()
        current_time = now_wat.time()
        
        # Check if it's Sunday
        if current_day == 6:
            return "⏰ We're currently closed. Our business hours are Monday to Saturday, 9:00 AM to 6:00 PM (WAT).\n\n📧 Our agents will reach out to you via email as soon as we're open. Please leave your message and we'll get back to you during business hours!"
        
        open_time = time(9, 0)
        close_time = time(18, 0)
        
        # Check if before opening
        if current_time < open_time:
            return f"⏰ We're currently closed. Our business hours are Monday to Saturday, 9:00 AM to 6:00 PM (WAT). We'll be open at 9:00 AM today.\n\n📧 Our agents will reach out to you via email as soon as we're open. Please leave your message and we'll get back to you during business hours!"
        
        # Check if after closing
        if current_time > close_time:
            return f"⏰ We're currently closed. Our business hours are Monday to Saturday, 9:00 AM to 6:00 PM (WAT). We'll be open tomorrow at 9:00 AM.\n\n📧 Our agents will reach out to you via email as soon as we're open. Please leave your message and we'll get back to you during business hours!"
        
        return None  # Within business hours
    except Exception:
        return None


def check_agent_availability():
    """Check if any agents are available"""
    try:
        # Ensure Agent profiles exist for staff users
        from django.contrib.auth.models import User
        staff_users = User.objects.filter(is_staff=True, is_active=True)
        for user in staff_users:
            if not hasattr(user, 'agent_profile'):
                Agent.objects.get_or_create(
                    user=user,
                    defaults={
                        'is_available': True,
                        'max_concurrent_chats': 5,
                        'current_chats': 0
                    }
                )
        
        available_agents = Agent.objects.filter(
            is_available=True,
            user__is_active=True,
            current_chats__lt=F('max_concurrent_chats')
        )
        return available_agents.exists()
    except Exception as e:
        print(f"Error checking agent availability: {e}")
        return False


def can_connect_to_agent():
    """Check if customer can connect to agent (business hours + availability)"""
    return check_business_hours() and check_agent_availability()


def generate_ticket_number():
    """Generate unique ticket number"""
    import random
    import string
    prefix = "TKT"
    timestamp = datetime.now().strftime("%Y%m%d")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{timestamp}-{random_part}"


def create_ticket(session, title, description, priority='medium'):
    """Create a support ticket"""
    ticket = Ticket.objects.create(
        session=session,
        ticket_number=generate_ticket_number(),
        title=title,
        description=description,
        priority=priority
    )
    
    # Notify admins about new ticket
    admins = User.objects.filter(is_staff=True)
    for admin in admins:
        Notification.objects.create(
            user=admin,
            notification_type='ticket',
            title=f'New Ticket: {ticket.ticket_number}',
            message=f'{title} - {description[:100]}...',
            related_session=session
        )
    
    # Send email notification to customer
    send_ticket_email_notification(ticket, session)
    
    return ticket


def send_ticket_email_notification(ticket, session):
    """Send email notification to customer when ticket is created"""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        
        # Get customer email
        customer_email = session.customer_email
        if not customer_email:
            print(f"No customer email found for session {session.session_id}")
            return False
        
        customer_name = session.customer_name or "Customer"
        
        subject = f"Support Ticket Created - {ticket.ticket_number}"
        message = f"""
Hello {customer_name},

Thank you for contacting Novyra. We have created a support ticket for your inquiry.

Ticket Number: {ticket.ticket_number}
Title: {ticket.title}
Priority: {ticket.priority.upper()}
Status: {ticket.status.upper()}

Description:
{ticket.description}

Our team will review your ticket and respond as soon as possible. You will receive an email notification once your ticket is updated.

If you have any questions or need to provide additional information, please reply to this email or contact us during business hours:
Monday to Saturday, 9:00 AM to 6:00 PM (WAT)

Best regards,
Novyra Support Team
        """
        
        # Send email
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'support@novyra.agency',
            recipient_list=[customer_email],
            fail_silently=False,
        )
        
        # Mark ticket as customer notified
        ticket.customer_notified = True
        ticket.save(update_fields=['customer_notified'])
        
        return True
    except Exception as e:
        print(f"Error sending ticket email notification: {e}")
        return False


def mark_message_as_read(message, user):
    """Mark a message as read by a user"""
    try:
        from django.utils import timezone
        message.is_read = True
        message.read_at = timezone.now()
        message.read_by = user
        message.save(update_fields=['is_read', 'read_at', 'read_by'])
        return True
    except Exception as e:
        print(f"Error marking message as read: {e}")
        return False


def save_conversation_learning(session, user_message, ai_response, intent, confidence, escalated=False):
    """Save conversation data for ML learning"""
    ConversationLearning.objects.create(
        session=session,
        user_message=user_message,
        ai_response=ai_response,
        intent_detected=intent,
        confidence=confidence,
        escalated=escalated
    )


def get_common_questions():
    """Get common questions for option buttons"""
    from .models import KnowledgeBase
    faqs = KnowledgeBase.objects.filter(category='faq', is_active=True).order_by('-priority')[:5]
    return [{'id': faq.id, 'title': faq.title, 'content': faq.content} for faq in faqs]


def send_after_hours_email_notification(session, message_content):
    """Send email notification to agents when customer contacts after hours"""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from django.contrib.auth.models import User
        
        # Get agent emails
        agents = User.objects.filter(is_staff=True, is_active=True)
        agent_emails = [agent.email for agent in agents if agent.email]
        
        if not agent_emails:
            # Fallback to admin email if no agent emails
            agent_emails = [settings.ADMINS[0][1]] if hasattr(settings, 'ADMINS') and settings.ADMINS else []
        
        if not agent_emails:
            print("No agent emails configured for after-hours notifications")
            return False
        
        # Prepare email content
        customer_name = session.customer_name or "Customer"
        customer_email = session.customer_email or "Not provided"
        customer_phone = session.customer_phone or "Not provided"
        
        subject = f"After-Hours Customer Message - Session {session.session_id[:8]}"
        message = f"""
Hello,

You have received a new customer message outside business hours.

Session ID: {session.session_id}
Customer Name: {customer_name}
Customer Email: {customer_email}
Customer Phone: {customer_phone}

Message:
{message_content}

Business Hours: Monday to Saturday, 9:00 AM to 6:00 PM (WAT)

Please respond to this customer during business hours.

You can view the full conversation at: {settings.FRONTEND_URL if hasattr(settings, 'FRONTEND_URL') else 'https://yourdomain.com'}/dashboard/?session={session.session_id}

Best regards,
Novyra AI Assistant
        """
        
        # Send email
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@novyra.agency',
            recipient_list=agent_emails,
            fail_silently=False,
        )
        
        return True
    except Exception as e:
        print(f"Error sending after-hours email notification: {e}")
        return False


def scrape_website_content(url: str) -> dict:
    """
    Scrape content from a website URL and store it in WebsiteContent model
    Returns: {'success': bool, 'message': str, 'content': WebsiteContent or None}
    """
    try:
        # Make request to URL
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title
        title = soup.find('title')
        title_text = title.get_text().strip() if title else None
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Extract main content
        # Try to find main content area
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=lambda x: x and ('content' in x.lower() or 'main' in x.lower()))
        
        if main_content:
            content_text = main_content.get_text(separator=' ', strip=True)
        else:
            # Fallback to body
            body = soup.find('body')
            content_text = body.get_text(separator=' ', strip=True) if body else ''
        
        # Clean up content (remove extra whitespace)
        content_text = ' '.join(content_text.split())
        
        # Extract metadata (headings, links)
        headings = [h.get_text().strip() for h in soup.find_all(['h1', 'h2', 'h3'])[:10]]
        links = [{'text': a.get_text().strip(), 'href': a.get('href', '')} for a in soup.find_all('a', href=True)[:20]]
        
        metadata = {
            'headings': headings,
            'links': links,
        }
        
        # Create or update WebsiteContent
        website_content, created = WebsiteContent.objects.update_or_create(
            url=url,
            defaults={
                'title': title_text,
                'content': content_text[:10000],  # Limit content length
                'metadata': metadata,
                'is_active': True,
            }
        )
        
        return {
            'success': True,
            'message': 'Website content scraped successfully' if created else 'Website content updated successfully',
            'content': website_content
        }
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'message': f'Error fetching website: {str(e)}',
            'content': None
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'Error scraping website: {str(e)}',
            'content': None
        }


def create_default_faqs():
    """Create default FAQ entries for Novyra Marketing"""
    default_faqs = [
        {
            'title': 'What services does Novyra offer?',
            'category': 'faq',
            'keywords': 'services, what do you offer, what services, offerings',
            'content': """Novyra Marketing offers comprehensive digital marketing services including:

📱 Social Media Marketing - Complete management across Instagram, Facebook, and TikTok
🎨 Branding - Logo design, brand style guides, and brand identity development
📊 Digital Campaigns - Lead generation, product launches, and awareness campaigns
✍️ Content Strategy - SEO-optimized blogs, video scripts, website copy, and email marketing
💰 Advertising - Paid media management on Google, Facebook, Instagram, and LinkedIn

All services are designed to help build brands that scale and drive measurable results.""",
            'intent': 'services',
            'priority': 10,
        },
        {
            'title': 'How much do your services cost?',
            'category': 'faq',
            'keywords': 'pricing, cost, price, how much, packages, plans',
            'content': """Novyra offers three social media management packages:

📦 BASIC - ₦30,000/month
• 3 Branded Posts/Month
• Social Media Setup (up to 3 platforms)
• Ad Account Setup
• 1 Promotional Video

📦 PREMIUM - ₦45,000/month
• 6 Branded Posts/Month
• Weekly Performance Check-in
• 3 Promotional Videos
• All Basic features

📦 ELITE - ₦65,000/month
• 8 Branded Posts/Month
• Full Social Media Management
• 5 Promotional Videos
• All Premium features

Contact us for custom pricing on other services like branding, campaigns, and content strategy!""",
            'intent': 'pricing',
            'priority': 10,
        },
        {
            'title': 'What are your business hours?',
            'category': 'faq',
            'keywords': 'hours, business hours, when are you open, available, contact hours',
            'content': """Our Business Hours:
🕐 Monday to Saturday: 9:00 AM to 6:00 PM (WAT)
🚫 Closed on Sundays

We're here to help you during business hours. If you contact us outside these hours, our agents will reach out to you via email as soon as we're open!""",
            'intent': 'business_hours',
            'priority': 9,
        },
        {
            'title': 'How long does it take to see results?',
            'category': 'faq',
            'keywords': 'results, how long, timeline, when will I see results, time frame',
            'content': """Results vary depending on the service and your goals:

📱 Social Media: You'll see engagement improvements within 2-4 weeks, with significant growth in 2-3 months
🎨 Branding: Complete brand identity packages typically take 4-6 weeks
📊 Campaigns: Initial results can be seen within 1-2 weeks, with optimization ongoing
✍️ Content: SEO content starts ranking in 3-6 months, while engagement content shows results faster

We provide regular performance reports so you can track progress. Our team is committed to delivering measurable results!""",
            'intent': 'timeline',
            'priority': 8,
        },
        {
            'title': 'Do you work with small businesses?',
            'category': 'faq',
            'keywords': 'small business, startups, small companies, new business',
            'content': """Absolutely! We work with businesses of all sizes, from startups to established companies.

Our Basic package is perfect for small businesses looking to establish their online presence. We understand that every business has unique needs and budgets, so we offer flexible packages and custom solutions.

Whether you're just starting out or looking to scale, we're here to help you build a brand that grows with your business.""",
            'intent': 'small_business',
            'priority': 7,
        },
        {
            'title': 'Can I see examples of your work?',
            'category': 'faq',
            'keywords': 'portfolio, examples, work, case studies, samples',
            'content': """Yes! We'd love to show you examples of our work. 

You can:
• Visit our website to see case studies and client testimonials
• Check out our social media accounts to see our content quality
• Request a portfolio presentation tailored to your industry

Contact us and we'll share relevant examples that match your business needs and goals.""",
            'intent': 'portfolio',
            'priority': 6,
        },
    ]
    
    from .models import KnowledgeBase
    
    created_count = 0
    for faq_data in default_faqs:
        faq, created = KnowledgeBase.objects.get_or_create(
            title=faq_data['title'],
            defaults=faq_data
        )
        if created:
            created_count += 1
    
    return created_count

