import yfinance as yf
from datetime import datetime
import random
import json

class WarrenBuffettAI:
    def __init__(self):
        self.investment_principles = [
            "Rule No. 1: Never lose money. Rule No. 2: Never forget Rule No. 1.",
            "Price is what you pay. Value is what you get.",
            "It's far better to buy a wonderful company at a fair price than a fair company at a wonderful price.",
            "Only buy something that you'd be perfectly happy to hold if the market shut down for 10 years.",
            "Risk comes from not knowing what you're doing.",
            "The most important quality for an investor is temperament, not intellect.",
            "Be fearful when others are greedy, and greedy when others are fearful.",
            "Our favorite holding period is forever.",
            "Time is the friend of the wonderful company, the enemy of the mediocre."
        ]
        
        self.value_metrics = {
            'pe_ratio': {'good': 15, 'max': 25},
            'debt_to_equity': {'good': 0.5, 'max': 1.5},
            'current_ratio': {'good': 1.5, 'min': 1.0},
            'profit_margin': {'good': 0.15, 'min': 0.10},
            'roe': {'good': 0.15, 'min': 0.10}
        }

        self.conversation_topics = {
            'investment_strategy': {
                'keywords': ['strategy', 'approach', 'invest', 'method', 'philosophy', 'principles'],
                'responses': [
                    "My investment strategy is simple: find wonderful businesses with durable competitive advantages, run by honest and competent management teams, and buy them at reasonable prices.",
                    "I focus on businesses I can understand. If I can't understand how a company makes money in 10 minutes, I move on to the next one.",
                    "I look for companies with strong moats - sustainable competitive advantages that protect their profits from competitors.",
                    "The key is to invest in businesses, not stocks. Think like a business owner, not a trader."
                ]
            },
            'market_timing': {
                'keywords': ['timing', 'when', 'buy', 'sell', 'market timing', 'entry', 'exit'],
                'responses': [
                    "I don't try to time the market. It's not about timing the market, it's about time in the market.",
                    "The best time to invest was yesterday. The second best time is today. The worst time is tomorrow.",
                    "If you wait for the robins, spring will be over.",
                    "Trying to time the market is a fool's game. Instead, make investing a lifelong process."
                ]
            },
            'diversification': {
                'keywords': ['diversify', 'diversification', 'portfolio', 'spread', 'allocation'],
                'responses': [
                    "Wide diversification is only required when investors do not understand what they are doing.",
                    "Put all your eggs in one basket, but watch that basket very carefully.",
                    "I believe in extreme diversification for those who don't know how to analyze businesses.",
                    "Risk comes from not knowing what you're doing. If you know what you're doing, concentrated positions can make sense."
                ]
            },
            'value_investing': {
                'keywords': ['value', 'intrinsic', 'worth', 'valuation', 'cheap', 'expensive'],
                'responses': [
                    "Price is what you pay, value is what you get. Focus on buying wonderful businesses below their intrinsic value.",
                    "The key is not to determine what's going to happen, but to determine what's happening now.",
                    "I'd rather buy a wonderful company at a fair price than a fair company at a wonderful price.",
                    "The stock market is a device for transferring money from the impatient to the patient."
                ]
            },
            'management': {
                'keywords': ['management', 'ceo', 'leadership', 'executives', 'board'],
                'responses': [
                    "When we own portions of outstanding businesses with outstanding managements, our favorite holding period is forever.",
                    "Look for three things in a business: smart people, decent returns on capital, and a reasonable price.",
                    "I try to invest in businesses that are so wonderful that an idiot can run them. Because sooner or later, one will.",
                    "Somebody once said that in looking for people to hire, you look for three qualities: integrity, intelligence, and energy. But if you don't have the first, the other two will kill you."
                ]
            },
            'competitive_advantage': {
                'keywords': ['moat', 'advantage', 'competitive', 'competition', 'barrier'],
                'responses': [
                    "The key to investing is determining the competitive advantage of any given business and, above all, the durability of that advantage.",
                    "Look for companies with wide moats - sustainable competitive advantages that protect their profits from competitors.",
                    "Economic goodwill - the ability to earn above-average returns on capital - is what creates real value.",
                    "A truly great business must have an enduring 'moat' that protects excellent returns on invested capital."
                ]
            },
            'risk_management': {
                'keywords': ['risk', 'downside', 'protect', 'safety', 'margin', 'loss'],
                'responses': [
                    "Risk comes from not knowing what you're doing. The more you know about a business, the less risk you take.",
                    "Never test the depth of a river with both feet. Always maintain a margin of safety.",
                    "If you're smart about when you buy, you don't have to be smart about when you sell.",
                    "The first rule of investment is don't lose. The second rule is don't forget the first rule."
                ]
            },
            'market_psychology': {
                'keywords': ['psychology', 'emotion', 'fear', 'greed', 'sentiment', 'behavior'],
                'responses': [
                    "Be fearful when others are greedy, and greedy when others are fearful.",
                    "The market is a device for transferring money from the impatient to the patient.",
                    "What the wise do in the beginning, fools do in the end.",
                    "You can't predict how people will behave. But you can profit from it."
                ]
            },
            'long_term': {
                'keywords': ['long term', 'patience', 'time', 'horizon', 'hold'],
                'responses': [
                    "Someone's sitting in the shade today because someone planted a tree a long time ago.",
                    "If you aren't willing to own a stock for 10 years, don't even think about owning it for 10 minutes.",
                    "Time is the friend of the wonderful company, the enemy of the mediocre.",
                    "Our favorite holding period is forever. If you don't feel comfortable owning something for 10 years, then don't own it for 10 minutes."
                ]
            },
            'circle_of_competence': {
                'keywords': ['understand', 'knowledge', 'competence', 'circle', 'expertise'],
                'responses': [
                    "Never invest in a business you cannot understand.",
                    "Stay within your circle of competence. It's not how big the circle is that counts, it's how well you define the perimeter.",
                    "Risk comes from not knowing what you're doing. Stick to what you understand.",
                    "You don't need to be an expert on every company, but you need to be able to understand the business model and its economics."
                ]
            }
        }

    def get_conversation_response(self, user_message, context=None):
        """Handle general conversation with users"""
        try:
            # Convert message to lowercase for easier matching
            message = user_message.lower()
            
            # Check if it's a stock analysis request
            if any(keyword in message for keyword in ['analyze', 'analysis', 'look at', 'what about', 'think of']) and any(word.isupper() for word in user_message.split()):
                ticker = next((word for word in user_message.split() if word.isupper()), None)
                if ticker:
                    return self.analyze_stock(ticker)

            # Check if it's a portfolio advice request
            if any(keyword in message for keyword in ['portfolio', 'holdings', 'positions', 'diversification']):
                if context and 'portfolio_data' in context:
                    return self.get_advice(context['portfolio_data'])
                else:
                    return {
                        'response': "I'd be happy to look at your portfolio, but I'll need to see your holdings first. Could you share your current positions with me?",
                        'type': 'portfolio_request'
                    }

            # Check for topic matches
            for topic, data in self.conversation_topics.items():
                if any(keyword in message for keyword in data['keywords']):
                    response = random.choice(data['responses'])
                    related_topics = self._get_related_topics(topic)
                    
                    return {
                        'response': response,
                        'type': topic,
                        'quote': random.choice(self.investment_principles),
                        'follow_up': f"Would you like to know more about {related_topics}?",
                        'related_topics': list(related_topics)
                    }

            # Handle market condition questions
            if any(keyword in message for keyword in ['market', 'economy', 'recession', 'bull', 'bear']):
                return {
                    'response': self._get_market_wisdom(),
                    'type': 'market_wisdom',
                    'quote': "Be fearful when others are greedy, and greedy when others are fearful."
                }

            # Handle valuation questions
            if any(keyword in message for keyword in ['value', 'worth', 'valuation', 'price']):
                return {
                    'response': self._get_valuation_wisdom(),
                    'type': 'valuation_wisdom',
                    'quote': "Price is what you pay. Value is what you get."
                }

            # Handle risk-related questions
            if any(keyword in message for keyword in ['risk', 'safe', 'danger', 'protect']):
                return {
                    'response': self._get_risk_wisdom(),
                    'type': 'risk_wisdom',
                    'quote': "Risk comes from not knowing what you're doing."
                }

            # Default response with investment wisdom
            return {
                'response': self._get_general_wisdom(),
                'type': 'general_wisdom',
                'quote': random.choice(self.investment_principles),
                'follow_up': "What aspect of investing would you like to discuss?"
            }

        except Exception as e:
            return {
                'response': "Even the best investors face uncertainty sometimes. Could you rephrase your question?",
                'type': 'error',
                'error': str(e)
            }

    def _get_related_topics(self, current_topic):
        """Get related topics for follow-up questions"""
        topic_relationships = {
            'investment_strategy': ['value_investing', 'long_term', 'circle_of_competence'],
            'market_timing': ['market_psychology', 'risk_management', 'long_term'],
            'diversification': ['risk_management', 'circle_of_competence', 'portfolio'],
            'value_investing': ['competitive_advantage', 'management', 'circle_of_competence'],
            'management': ['competitive_advantage', 'long_term', 'circle_of_competence'],
            'competitive_advantage': ['value_investing', 'management', 'long_term'],
            'risk_management': ['market_psychology', 'diversification', 'circle_of_competence'],
            'market_psychology': ['market_timing', 'risk_management', 'long_term'],
            'long_term': ['investment_strategy', 'value_investing', 'competitive_advantage'],
            'circle_of_competence': ['investment_strategy', 'risk_management', 'value_investing']
        }
        
        related = topic_relationships.get(current_topic, [])
        return [topic.replace('_', ' ').title() for topic in related]

    def _get_market_wisdom(self):
        """Generate wisdom about market conditions"""
        market_wisdom = [
            "Be fearful when others are greedy, and greedy when others are fearful.",
            "The market is a device for transferring money from the impatient to the patient.",
            "Market fluctuations are your friend, not your enemy. Embrace them.",
            "The stock market is designed to transfer money from the active to the patient."
        ]
        return random.choice(market_wisdom)

    def _get_valuation_wisdom(self):
        """Generate wisdom about valuation"""
        valuation_wisdom = [
            "Price is what you pay, value is what you get. Focus on the intrinsic value.",
            "It's better to buy a wonderful company at a fair price than a fair company at a wonderful price.",
            "The value of a business is the sum of all the money it will make in the future.",
            "Look for businesses that can maintain a competitive advantage and earn high returns on capital."
        ]
        return random.choice(valuation_wisdom)

    def _get_risk_wisdom(self):
        """Generate wisdom about risk management"""
        risk_wisdom = [
            "Risk comes from not knowing what you're doing. Invest in what you understand.",
            "The most important quality for an investor is temperament, not intellect.",
            "Never test the depth of a river with both feet.",
            "Keep a margin of safety in your investments. It's better to be approximately right than precisely wrong."
        ]
        return random.choice(risk_wisdom)

    def _get_general_wisdom(self):
        """Generate general investment wisdom"""
        general_wisdom = [
            "The best investment you can make is in yourself.",
            "Time is the friend of the wonderful company, the enemy of the mediocre.",
            "Our favorite holding period is forever.",
            "Wide diversification is only required when investors do not understand what they are doing.",
            "The key to investing is determining the competitive advantage of any given business and, above all, the durability of that advantage."
        ]
        return random.choice(general_wisdom)

    def analyze_stock(self, ticker):
        """Analyze a stock using Warren Buffett's principles"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Get key metrics
            pe_ratio = info.get('forwardPE', info.get('trailingPE', 0))
            debt_to_equity = info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0
            profit_margin = info.get('profitMargins', 0)
            roe = info.get('returnOnEquity', 0)
            
            # Analysis based on Buffett's principles
            analysis = []
            
            # PE Ratio Analysis
            if pe_ratio > 0:
                if pe_ratio <= self.value_metrics['pe_ratio']['good']:
                    analysis.append(f"The P/E ratio of {pe_ratio:.2f} looks attractive. As I always say, price is what you pay, value is what you get.")
                elif pe_ratio <= self.value_metrics['pe_ratio']['max']:
                    analysis.append(f"The P/E ratio of {pe_ratio:.2f} is reasonable, but I prefer to see lower valuations. Remember, be fearful when others are greedy.")
                else:
                    analysis.append(f"The P/E ratio of {pe_ratio:.2f} is quite high. I prefer businesses that are reasonably priced relative to their earnings.")

            # Debt Analysis
            if debt_to_equity <= self.value_metrics['debt_to_equity']['good']:
                analysis.append("I like that this company maintains a conservative debt level. Good businesses rarely need to borrow heavily.")
            elif debt_to_equity <= self.value_metrics['debt_to_equity']['max']:
                analysis.append("The debt level is something to watch carefully. Remember, you never want to depend on the kindness of strangers in this business.")
            else:
                analysis.append("I'm concerned about the high debt levels. In business, I've seen many things go wrong, but rarely see things go wrong with little or no debt.")

            # Profitability Analysis
            if profit_margin >= self.value_metrics['profit_margin']['good']:
                analysis.append("The profit margins are excellent. I love businesses with strong pricing power and efficient operations.")
            elif profit_margin >= self.value_metrics['profit_margin']['min']:
                analysis.append("The profit margins are decent, but there might be room for improvement. I prefer businesses with strong competitive advantages.")
            else:
                analysis.append("The profit margins concern me. I look for businesses that can maintain strong profitability over time.")

            # Return on Equity Analysis
            if roe >= self.value_metrics['roe']['good']:
                analysis.append("The return on equity is impressive. This often indicates a business with a strong competitive advantage.")
            elif roe >= self.value_metrics['roe']['min']:
                analysis.append("The return on equity is acceptable, but I prefer to see higher returns on shareholders' equity.")
            else:
                analysis.append("The return on equity is lower than I'd like. I look for businesses that can generate good returns without requiring too much capital.")

            # Add a Buffett-style conclusion
            if len(analysis) >= 3:
                overall_sentiment = self._get_overall_sentiment(pe_ratio, debt_to_equity, profit_margin, roe)
                analysis.append(self._get_conclusion(overall_sentiment))

            return {
                'analysis': analysis,
                'metrics': {
                    'PE Ratio': f"{pe_ratio:.2f}",
                    'Debt to Equity': f"{debt_to_equity:.2f}",
                    'Profit Margin': f"{profit_margin:.2%}",
                    'Return on Equity': f"{roe:.2%}"
                },
                'quote': random.choice(self.investment_principles)
            }

        except Exception as e:
            return {
                'analysis': ["I always say you should invest in what you understand. Right now, I don't have enough information to make a proper analysis of this company."],
                'metrics': {},
                'quote': "Risk comes from not knowing what you're doing."
            }

    def get_advice(self, portfolio_data):
        """Provide Warren Buffett style advice based on portfolio composition"""
        try:
            advice = []
            
            # Check portfolio diversification
            if len(portfolio_data['positions']) < 5:
                advice.append("I notice your portfolio is quite concentrated. While I believe in concentration over diversification, make sure you really understand these businesses inside and out.")
            elif len(portfolio_data['positions']) > 20:
                advice.append("You seem to have quite a few positions. Remember, wide diversification is only required when investors don't understand what they're doing.")

            # Check individual position sizes
            total_value = portfolio_data['total_value']
            large_positions = [p for p in portfolio_data['positions'] if (p['position_value'] / total_value) > 0.20]
            
            if large_positions:
                advice.append(f"You have significant positions in {', '.join([p['ticker'] for p in large_positions])}. That's fine if you have strong conviction, but remember that risk comes from not knowing what you're doing.")

            # Add general wisdom
            advice.append(random.choice([
                "Remember, the stock market is designed to transfer money from the active to the patient.",
                "The best investment you can make is in yourself. Always be learning.",
                "Look for wonderful businesses at fair prices, rather than fair businesses at wonderful prices.",
                "The key to investing is determining the competitive advantage of any given company and, above all, the durability of that advantage."
            ]))

            return {
                'advice': advice,
                'wisdom_quote': random.choice(self.investment_principles)
            }

        except Exception as e:
            return {
                'advice': ["The most important thing in investing is to know what you're doing. If you're unsure, consider index funds."],
                'wisdom_quote': "Risk comes from not knowing what you're doing."
            }

    def _get_overall_sentiment(self, pe_ratio, debt_to_equity, profit_margin, roe):
        """Determine overall sentiment based on metrics"""
        score = 0
        if pe_ratio <= self.value_metrics['pe_ratio']['good']: score += 1
        if debt_to_equity <= self.value_metrics['debt_to_equity']['good']: score += 1
        if profit_margin >= self.value_metrics['profit_margin']['good']: score += 1
        if roe >= self.value_metrics['roe']['good']: score += 1
        
        if score >= 3: return "positive"
        elif score >= 2: return "neutral"
        return "negative"

    def _get_conclusion(self, sentiment):
        """Get a Buffett-style conclusion based on sentiment"""
        conclusions = {
            "positive": [
                "Overall, this business shows many of the characteristics I look for. But remember, a great company isn't always a great investment if the price isn't right.",
                "This company appears to have some of the qualities I appreciate: good returns, reasonable debt, and solid profitability. But always do your own homework."
            ],
            "neutral": [
                "While there are some positive aspects to this business, I'd want to dig deeper into their competitive advantages and long-term prospects.",
                "The numbers are mixed. Remember, it's better to buy a wonderful company at a fair price than a fair company at a wonderful price."
            ],
            "negative": [
                "I see several red flags here. Remember, Rule No.1 is never lose money. Rule No.2 is never forget Rule No.1.",
                "The metrics suggest this business might not have the kind of durable competitive advantage I typically look for. Be careful."
            ]
        }
        return random.choice(conclusions[sentiment]) 