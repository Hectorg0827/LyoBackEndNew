from __future__ import annotations
"""
AI Avatar module for personalized learning interactions.

This module provides the core functionality for Lyo's AI Avatar,
enabling natural conversation, context retention, and personalized tutoring.
"""
import asyncio
import json
import logging
import time
import random # Added import for random
import uuid # Added import for uuid
from abc import ABC, abstractmethod
from collections import defaultdict # Added import for defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime # Added import for datetime
from enum import Enum
from typing import Any, Dict, Optional, List, Tuple, Union, Callable, Literal, AsyncGenerator # Added Literal and AsyncGenerator

from api.core.config import get_ai_settings, AISettings
from api.core import ai_config # Added import for ai_config
from api.services.ai import AIService, ChatRequest, ChatResponseChunk # Added ChatRequest, ChatResponseChunk
from api.core.content_retrieval import ContentRetrievalService
from api.core.content_assembly import ContentAssemblyService, LearningStyle, LearningPace # Added LearningStyle, LearningPace
from api.services.content import ContentService # Added import
from api.db.avatar_firestore import AvatarFirestore # Assuming this is where it's defined
from api.db.avatar_cache import (
    cache_avatar_context,
    get_cached_avatar_context,
    invalidate_avatar_cache,
    get_cache_config # Added import for get_cache_config
)
from api.core.telemetry import meter # Added import for meter

# Placeholder for ContentService as its file (api/services/content.py) is not provided
# This is required for AIService instantiation.
class ContentService: # Placeholder
    async def search_books(self, query: str, max_results: int = 5) -> List[Any]:
        logger.info(f"[Placeholder ContentService] Searching books for query: {query}")
        return []
    async def search_videos(self, query: str, max_results: int = 5, safe_search: bool = True) -> List[Any]:
        logger.info(f"[Placeholder ContentService] Searching videos for query: {query}")
        return []
    async def search_podcasts(self, query: str, max_results: int = 5) -> List[Any]:
        logger.info(f"[Placeholder ContentService] Searching podcasts for query: {query}")
        return []
    async def search_courses(self, query: str, max_results: int = 5) -> List[Any]:
        logger.info(f"[Placeholder ContentService] Searching courses for query: {query}")
        return []
    # Add other methods AIService might depend on from ContentService if necessary

# Configure logging with proper formatting
logger = logging.getLogger(__name__)

# Create metrics
storage_latency = meter.create_histogram(
    name="avatar.storage.latency",
    description="Latency of avatar storage operations",
    unit="seconds"
)

storage_errors = meter.create_counter(
    name="avatar.storage.errors",
    description="Number of avatar storage operation errors"
)


class AgentType(str, Enum):
    """Types of learning agents."""
    ORCHESTRATOR = "orchestrator"
    TUTOR = "tutor"
    QUIZ = "quiz"
    CONTENT_CURATOR = "content_curator"
    MOTIVATIONAL = "motivational"


class LearningAgent(ABC):
    """Abstract base class for all learning agents."""

    def __init__(self, agent_type: AgentType, avatar_service: 'AvatarService'):
        self.agent_type = agent_type
        self.avatar_service = avatar_service # To access context, history, shared services
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def get_capabilities(self) -> List[str]:
        """Returns a list of capabilities this agent can handle (e.g., 'answer_question', 'generate_quiz')."""
        pass

    @abstractmethod
    async def handle_interaction(
        self,
        user_message: 'AvatarMessage',
        context: 'AvatarContext',
        conversation_history: List['AvatarMessage']
    ) -> 'AvatarMessage':
        """
        Processes a user interaction and returns the agent's response.
        Should utilize context and conversation history.
        """
        pass

    async def _get_shared_service(self, service_name: str) -> Any:
        """Helper to get shared services from AvatarService."""
        if hasattr(self.avatar_service, service_name):
            return getattr(self.avatar_service, service_name)
        self.logger.warning(f"Shared service '{service_name}' not found in AvatarService.")
        return None


class TutorAgent(LearningAgent):
    """Agent focused on explaining concepts and answering questions."""
    def __init__(self, avatar_service: 'AvatarService'):
        super().__init__(AgentType.TUTOR, avatar_service)
        self.ai_service = avatar_service.ai_service # Ensure ai_service is available

    async def get_capabilities(self) -> List[str]:
        return ["answer_question", "explain_concept", "socratic_dialogue", "clarify_doubt"]

    async def handle_interaction(
        self,
        user_message: 'AvatarMessage',
        context: 'AvatarContext',
        conversation_history: List['AvatarMessage']
    ) -> 'AvatarMessage':
        self.logger.info(f"TutorAgent handling interaction for user {context.user_id} with message: '{user_message.content}'")

        intent_data = await self.avatar_service._detect_intent(user_message.content, context)
        detected_intent = intent_data.get("intent", "unknown")
        entities = intent_data.get("entities", {})
        topic_from_intent = entities.get("topic")

        # Construct a more specific prompt for the LLM based on intent and context
        llm_request_message = user_message.content
        persona_to_use = context.persona # Default to context persona

        if detected_intent == "explain_concept":
            concept = topic_from_intent or user_message.content # Fallback to full message if no specific topic
            llm_request_message = f"Explain the concept of '{concept}'."
            if context.learning_style == "visual":
                llm_request_message += " Use analogies or examples that can be easily visualized."
            elif context.learning_style == "auditory":
                llm_request_message += " Explain it as if you were speaking in a podcast or lecture."
            # Add more learning style adaptations
            persona_to_use = AvatarPersona.EXPERT # Or TUTOR, depending on desired depth
            if context.current_module:
                 llm_request_message += f" Relate it to their current module: {context.current_module} if applicable."

        elif detected_intent == "answer_question": # Generic question
            llm_request_message = f"Answer the following question: {user_message.content}"
            if context.current_module:
                llm_request_message += f" The user is currently studying: {context.current_module}. Provide contextually relevant information if possible."
        
        elif detected_intent == "socratic_dialogue": # Placeholder for more complex Socratic logic
            llm_request_message = f"Engage in a Socratic dialogue about: {topic_from_intent or user_message.content}. Ask guiding questions to help the user explore the topic themselves."
            persona_to_use = AvatarPersona.TUTOR
        
        # Default handling if intent is unknown or general, or if it's a follow-up
        # The _generate_response method already includes history and general context

        self.logger.debug(f"TutorAgent LLM request: '{llm_request_message}', Persona: {persona_to_use.value}")

        response_data = await self.avatar_service._generate_response(
            message=llm_request_message, # This is now the more specific, agent-crafted message
            context=context,
            conversation=conversation_history,
            persona_override=persona_to_use
        )
        
        response_text = response_data.get("text", "I'm still learning how to explain that clearly. Could you ask in a different way?")
        metadata = {"agent_type": self.agent_type.value, **response_data.get("llm_metadata", {})}

        # Potentially add follow-up questions or resource suggestions based on the explanation
        if detected_intent == "explain_concept": # Sourcery: removed redundant response_text check (assuming response_text is generally non-empty)
            # Example: Ask if the user wants related resources
            # This could be a separate call or integrated into the LLM prompt
            pass # Add logic for follow-up actions if needed

        return AvatarMessage(content=response_text, role="avatar", metadata=metadata)


class QuizAgent(LearningAgent):
    """Agent responsible for generating and managing quizzes."""
    def __init__(self, avatar_service: 'AvatarService'):
        super().__init__(AgentType.QUIZ, avatar_service)
        self.ai_service = avatar_service.ai_service

    async def get_capabilities(self) -> List[str]:
        return ["start_quiz", "submit_answer", "get_quiz_results"]

    async def handle_interaction(
        self,
        user_message: 'AvatarMessage',
        context: 'AvatarContext',
        conversation_history: List['AvatarMessage']
    ) -> 'AvatarMessage':
        self.logger.info(f"Handling quiz interaction for user {context.user_id}")
        response_text = f"Quiz Agent: Ready for a quiz on {context.current_module or 'your current topic'}?"
        metadata = {"agent_type": self.agent_type.value}
        
        # Improved intent check for starting a quiz
        if "quiz" in user_message.content.lower() and ("start" in user_message.content.lower() or "give me" in user_message.content.lower() or "take" in user_message.content.lower()):
            if topic_for_quiz := (context.current_module or "general knowledge"): # Fallback topic # Sourcery: Use named expression
                self.logger.info(f"Attempting to generate quiz for topic: {topic_for_quiz}")
                try:
                    # Pass context as a dictionary
                    quiz_data = await self.ai_service.generate_quiz_for_topic(topic_for_quiz, context.to_dict())
                    if quiz_data and quiz_data.get("questions"):
                        response_text = f"Okay, here's a quiz on {topic_for_quiz}:\\n"
                        for i, q_item in enumerate(quiz_data.get("questions", [])):
                            response_text += f"Q{i+1}: {q_item.get('question_text')}\\n"
                            if q_item.get("options"):
                                for opt_idx, opt_val in enumerate(q_item.get("options", [])):
                                    response_text += f"  {chr(65+opt_idx)}. {opt_val}\\n"
                        metadata["quiz_data"] = quiz_data
                    else:
                        self.logger.warning(f"Quiz data for topic '{topic_for_quiz}' was empty or invalid.")
                        response_text = f"I couldn't come up with a quiz for '{topic_for_quiz}' right now. Maybe try another topic?"
                except Exception as e:
                    self.logger.error(f"Error generating quiz for topic '{topic_for_quiz}': {e}", exc_info=True)
                    response_text = "I had trouble preparing that quiz. Let's try something else."
            else:
                response_text = "What topic would you like a quiz on?"


        return AvatarMessage(content=response_text, role="avatar", metadata=metadata)


class ContentCurationAgent(LearningAgent):
    """Agent that suggests relevant learning materials."""
    def __init__(self, avatar_service: 'AvatarService'):
        super().__init__(AgentType.CONTENT_CURATOR, avatar_service)
        self.content_retrieval_service = avatar_service.content_retrieval_service

    async def get_capabilities(self) -> List[str]:
        return ["find_articles", "suggest_videos", "recommend_books", "find_resources"]

    async def handle_interaction(
        self,
        user_message: 'AvatarMessage',
        context: 'AvatarContext',
        conversation_history: List['AvatarMessage']
    ) -> 'AvatarMessage':
        self.logger.info(f"Handling content curation for user {context.user_id} with message: '{user_message.content}'")
        metadata = {"agent_type": self.agent_type.value}
        
        intent_data = await self.avatar_service._detect_intent(user_message.content, context)
        detected_intent = intent_data.get("intent")
        entities = intent_data.get("entities", {})
        
        search_query = user_message.content # Default query
        if detected_intent == "request_resource" and entities.get("query"):
            search_query = entities["query"]
        elif detected_intent == "explain_concept" and entities.get("topic"): # If user asks to explain something, might also want resources
            search_query = entities["topic"]
        elif context.current_module and \
             (not user_message.content or # Handle empty message if intent somehow routed here
              any(kw in user_message.content.lower() for kw in ["current topic", "this module", "related to this"])):
             search_query = context.current_module

        self.logger.info(f"ContentCurationAgent: Effective search query: '{search_query}'")

        try:
            # Pass context.to_dict() as user_preferences.
            # Assumes ContentRetrievalService.search_all_sources can use it.
            resources = await self.content_retrieval_service.search_all_sources(
                query=search_query, 
                user_preferences=context.to_dict()
            )

            if resources and any(isinstance(items, list) and len(items) > 0 for items in resources.values()):
                response_text = f"I found some resources related to '{search_query}':\n"
                resource_count = 0
                metadata["links"] = [] # Initialize links list in metadata

                for source, items in resources.items():
                    if items and isinstance(items, list):
                        # Check if items are dicts as expected
                        valid_items = [item for item in items if isinstance(item, dict)]
                        if not valid_items:
                            continue

                        response_text += f"\nFrom {source.replace('_', ' ').capitalize()}:\n"
                        for item in valid_items[:2]: # Show a couple from each source
                            title = item.get('title', 'Unknown title')
                            link = item.get('link')
                            snippet = item.get('snippet', '')
                            
                            response_text += f"- {title}"
                            if link:
                                response_text += f" (Link available in details)\n"
                                metadata["links"].append({"title": title, "url": link, "source": source})
                            else:
                                response_text += "\n"
                            
                            if snippet:
                                # Ensure snippet is a string before slicing
                                snippet_text = str(snippet)[:100] if snippet else ""
                                if snippet_text:
                                     response_text += f"  Snippet: {snippet_text}...\n"
                            resource_count +=1
                
                if resource_count == 0:
                    response_text = f"I looked for resources on '{search_query}' but couldn't find anything specific right now. Try rephrasing?"
                else:
                    metadata["suggested_resources"] = resources # Full data in metadata for client to use
            else:
                response_text = f"I couldn't find specific resources for '{search_query}' right now. Perhaps try a broader topic or different keywords?"
        except Exception as e:
            self.logger.error(f"Error retrieving content for query '{search_query}': {e}", exc_info=True)
            response_text = "I had some trouble finding resources at the moment. Please try again a bit later."
            metadata["error"] = str(e)
            
        return AvatarMessage(content=response_text, role="avatar", metadata=metadata)


class MotivationalAgent(LearningAgent):
    """Agent focused on providing encouragement and tracking goals."""
    def __init__(self, avatar_service: 'AvatarService'):
        super().__init__(AgentType.MOTIVATIONAL, avatar_service)

    async def get_capabilities(self) -> List[str]:
        return ["provide_encouragement", "check_goal_progress", "celebrate_achievement"]

    async def handle_interaction(
        self,
        user_message: 'AvatarMessage',
        context: 'AvatarContext',
        conversation_history: List['AvatarMessage']
    ) -> 'AvatarMessage':
        self.logger.info(f"Handling motivational interaction for user {context.user_id}")
        
        prompt_elements = ["Provide an encouraging, personalized, and supportive message."]
        user_display_name = context.user_id.split('@')[0] if '@' in context.user_id else context.user_id
        prompt_elements.append(f"The user's name is {user_display_name}.")
        
        if context.engagement_level < 0.4: # Lowered threshold for more proactive check
            prompt_elements.append("The user seems to be disengaged or struggling. Offer gentle encouragement and remind them of their strengths or the value of perseverance. Avoid sounding repetitive.")
            if context.strengths:
                prompt_elements.append(f"They have shown strength in: {', '.join(context.strengths)}.")
        
        if context.learning_goals:
            goal_to_mention = context.learning_goals[0]
            prompt_elements.append(f"Their primary learning goal is: '{goal_to_mention}'. Connect the encouragement to this goal.")

        if context.current_module:
            prompt_elements.append(f"They are currently focused on the module: '{context.current_module}'.")

        if context.learning_history:
            # Consider achievements within the last few days
            recent_achievements = [
                h for h in context.learning_history 
                if h.get("timestamp") and (time.time() - h.get("timestamp", 0)) < (86400 * 3) # Last 3 days
            ]
            if recent_achievements:
                completed_items_desc = []
                for ach in recent_achievements:
                    item_desc = ach.get('lesson_id', ach.get('module_id', 'something'))
                    if ach.get('module_id') and ach.get('lesson_id'):
                        item_desc = f"{ach.get('lesson_id')} in {ach.get('module_id')}"
                    elif ach.get('module_id'):
                        item_desc = f"progress in {ach.get('module_id')}"
                    completed_items_desc.append(item_desc)
                
                if completed_items_desc:
                    prompt_elements.append(f"Acknowledge their recent progress on: {', '.join(list(set(completed_items_desc)))}. Congratulate them specifically.")

        pending_tasks = [task for task in context.active_tasks if task.get("status") == "pending"]
        if pending_tasks:
            task_desc = pending_tasks[0].get("description", "their current task")
            prompt_elements.append(f"Gently remind and encourage them to continue or start working on '{task_desc}'.")
        elif not context.active_tasks and context.learning_goals: # No tasks, but has goals
             prompt_elements.append("Suggest they could set a new small task related to their goals or explore the current module further.")


        # If user explicitly asks for motivation, make it clear in the prompt for LLM
        if any(kw in user_message.content.lower() for kw in ["motivate", "encourage", "feeling down", "discouraged", "i'm stuck"]):
            llm_request_message = f"User explicitly asked for motivation. Their message: '{user_message.content}'. Based on this and the context, " + " ".join(prompt_elements)
        else: # Proactive motivation
            llm_request_message = " ".join(prompt_elements)
        
        response_data = await self.avatar_service._generate_response(
            message=llm_request_message,
            context=context,
            conversation=conversation_history,
            persona_override=AvatarPersona.COACH 
        )
        
        response_text = response_data.get("text")
        if not response_text: # Fallback if LLM fails or returns empty
            if context.engagement_level < 0.5:
                 response_text = f"Hey {user_display_name}! I noticed you might be a bit stuck. Remember why you started this journey! You've got this."
            elif context.learning_goals:
                 response_text = f"Remember your goal, {user_display_name}: {context.learning_goals[0]}. You're making progress!"
            else:
                 response_text = f"Keep up the great work, {user_display_name}! Every step forward counts."

        metadata = {"agent_type": self.agent_type.value, **response_data.get("llm_metadata", {})}
        
        return AvatarMessage(content=response_text, role="avatar", metadata=metadata)


class AvatarOrchestrator(LearningAgent):
    """
    Orchestrates interactions between the user and various specialized learning agents.
    """
    def __init__(self, avatar_service: 'AvatarService', agents: Dict[AgentType, LearningAgent]):
        super().__init__(AgentType.ORCHESTRATOR, avatar_service)
        self.agents = agents
        self.active_agent: Optional[LearningAgent] = None 

    async def get_capabilities(self) -> List[str]:
        return ["route_interaction"]

    async def handle_interaction(
        self,
        user_message: 'AvatarMessage',
        context: 'AvatarContext',
        conversation_history: List['AvatarMessage']
    ) -> 'AvatarMessage':
        self.logger.info(f"Orchestrator handling message from {context.user_id}: {user_message.content}")

        intent_data = await self.avatar_service._detect_intent(user_message.content)
        detected_intent = intent_data.get("intent", "unknown") # Default to unknown
        self.logger.debug(f"Detected intent: {detected_intent} for message: {user_message.content}")

        selected_agent: Optional[LearningAgent] = None

        # More robust intent-to-agent mapping
        if detected_intent == "request_quiz" or "quiz" in user_message.content.lower():
            selected_agent = self.agents.get(AgentType.QUIZ)
        elif detected_intent in ["ask_question", "explain_concept"] or any(kw in user_message.content.lower() for kw in ["explain", "what is", "how does"]):
            selected_agent = self.agents.get(AgentType.TUTOR)
        elif detected_intent == "request_resource" or any(kw in user_message.content.lower() for kw in ["find", "recommend", "suggest article", "show video"]):
            selected_agent = self.agents.get(AgentType.CONTENT_CURATOR)
        elif detected_intent == "request_motivation" or context.engagement_level < 0.4 or any(kw in user_message.content.lower() for kw in ["feeling down", "discouraged", "motivate me"]):
            selected_agent = self.agents.get(AgentType.MOTIVATIONAL)
        
        if not selected_agent: # Fallback
            self.logger.info("No specific agent matched by intent, defaulting to Tutor agent.")
            selected_agent = self.agents.get(AgentType.TUTOR)

        if selected_agent:
            self.logger.info(f"Routing to {selected_agent.agent_type.value} agent.")
            try:
                return await selected_agent.handle_interaction(user_message, context, conversation_history)
            except Exception as e:
                self.logger.error(f"Error during {selected_agent.agent_type.value} agent interaction: {e}", exc_info=True)
                return AvatarMessage(content="I encountered an issue trying to process that. Please try again.", role="avatar", metadata={"agent_type": AgentType.ORCHESTRATOR.value, "error": True, "original_agent_error": str(e)})
        else: # Should not happen if default is set
            self.logger.error("No agent available, including default. This is a configuration error.")
            # Fallback to a generic response using AvatarService's _generate_response
            response_data = await self.avatar_service._generate_response(
                message=user_message.content,
                context=context,
                conversation=conversation_history
            )
            return AvatarMessage(content=response_data.get("text", "I'm not sure how to help with that right now."), role="avatar", metadata={"agent_type": AgentType.ORCHESTRATOR.value, **response_data})


@dataclass
class AvatarPersona(str, Enum):
    """Types of personas the Avatar can adopt."""
    
    TUTOR = "tutor"  # Formal, educational
    COACH = "coach"  # Encouraging, motivational
    FRIEND = "friend"  # Casual, supportive
    EXPERT = "expert"  # Technical, detailed


@dataclass
class AvatarContext:
    """Context maintained across Avatar interactions."""
    
    user_id: str
    session_id: str = None
    topics_discussed: List[str] = field(default_factory=list)
    learning_goals: List[str] = field(default_factory=list)
    current_module: Optional[str] = None
    last_interaction_time: float = field(default_factory=time.time)
    sentiment_history: List[Dict[str, Any]] = field(default_factory=list)
    persona: AvatarPersona = AvatarPersona.TUTOR
    engagement_level: float = 1.0  # 0.0 to 1.0
    
    # Enhanced context attributes
    learning_style: Optional[str] = None  # visual, auditory, kinesthetic, etc.
    learning_pace: Optional[str] = None  # slow, moderate, fast
    strengths: List[str] = field(default_factory=list)  # Topics/subjects the user is strong in
    areas_for_improvement: List[str] = field(default_factory=list)  # Topics needing improvement
    learning_history: List[Dict[str, Any]] = field(default_factory=list)  # Completed modules/lessons
    active_tasks: List[Dict[str, Any]] = field(default_factory=list)  # Tasks assigned to user
    preferred_resources: List[str] = field(default_factory=list)  # Preferred resource types
    interaction_patterns: Dict[str, float] = field(default_factory=lambda: {
        "avg_response_time": 0,
        "avg_message_length": 0,
        "session_count": 0,
        "total_interactions": 0
    })
    
    def __post_init__(self):
        """Initialize session_id if not provided."""
        if not self.session_id:
            self.session_id = f"session_{int(time.time())}"
        
    def update_engagement(self, engagement_score: float):
        """Update the user's engagement level."""
        # Smooth the engagement level with an exponential moving average
        self.engagement_level = 0.7 * self.engagement_level + 0.3 * max(0.0, min(1.0, engagement_score))
        
    def add_topic(self, topic: str):
        """Add a topic to the discussed topics list."""
        if topic and topic not in self.topics_discussed:
            self.topics_discussed.append(topic)
    
    def set_learning_goal(self, goal: str):
        """Set a learning goal for the user."""
        if goal and goal not in self.learning_goals:
            self.learning_goals.append(goal)
    
    def clear_current_module(self):
        """Clear the current module."""
        self.current_module = None
        
    def set_current_module(self, module_id: str):
        """Set the current module being studied."""
        self.current_module = module_id
        
    def record_sentiment(self, sentiment: str, confidence: float):
        """Record user sentiment."""
        if not sentiment:
            return
            
        self.sentiment_history.append({
            "sentiment": sentiment,
            "confidence": confidence,
            "timestamp": time.time()
        })
        
    def update_interaction_time(self):
        """Update the last interaction time."""
        self.last_interaction_time = time.time()
        
    def switch_persona(self, persona: AvatarPersona):
        """Switch the avatar's persona."""
        self.persona = persona
        
    def get_recent_sentiment(self, window_seconds: int = 300) -> Optional[str]:
        """Get the user's recent sentiment within a time window."""
        if not self.sentiment_history:
            return None
            
        current_time = time.time()
        recent_sentiments = [
            s for s in self.sentiment_history 
            if current_time - s["timestamp"] <= window_seconds # Corrected: was missing 'self.' if it were a member, but it's a param
        ]
        
        if not recent_sentiments:
            return None
            
        # Return the most frequent sentiment
        sentiment_counts = {}
        for s in recent_sentiments:
            sentiment = s["sentiment"]
            sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
            
        return max(sentiment_counts, key=sentiment_counts.get)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for storage."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AvatarContext':
        """Create context from dictionary."""
        # Handle persona conversion from string to enum
        if "persona" in data and isinstance(data["persona"], str):
            try:
                data["persona"] = AvatarPersona(data["persona"])
            except ValueError:
                data["persona"] = AvatarPersona.TUTOR
                
        # Filter out any unexpected keys to avoid errors with dataclass
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        
        return cls(**filtered_data)

    def set_learning_style(self, style: str) -> None:
        """Set the user's preferred learning style."""
        self.learning_style = style
        
    def set_learning_pace(self, pace: str) -> None:
        """Set the user's learning pace."""
        self.learning_pace = pace
    
    def add_strength(self, topic: str) -> None:
        """Add a topic to the user's strengths."""
        if topic and topic not in self.strengths:
            self.strengths.append(topic)
    
    def add_area_for_improvement(self, topic: str) -> None:
        """Add a topic to the user's areas for improvement."""
        if topic and topic not in self.areas_for_improvement:
            self.areas_for_improvement.append(topic)
    
    def add_completed_learning(self, module_id: str, lesson_id: str, score: Optional[float] = None) -> None:
        """Record a completed module/lesson."""
        self.learning_history.append({
            "module_id": module_id,
            "lesson_id": lesson_id,
            "score": score,
            "timestamp": time.time()
        })
    
    def add_task(self, task_type: str, description: str, due_date: Optional[float] = None, 
                 resource_links: Optional[List[str]] = None) -> str:
        """Add a task for the user."""
        task_id = f"task_{len(self.active_tasks) + 1}_{int(time.time())}"
        self.active_tasks.append({
            "task_id": task_id,
            "type": task_type,
            "description": description,
            "created_at": time.time(),
            "due_date": due_date,
            "resource_links": resource_links or [],
            "status": "pending"
        })
        return task_id
    
    def complete_task(self, task_id: str) -> bool:
        """Mark a task as completed."""
        for task in self.active_tasks:
            if task["task_id"] == task_id:
                task["status"] = "completed"
                task["completed_at"] = time.time()
                return True
        return False
    
    def add_preferred_resource(self, resource_type: str) -> None:
        """Add a preferred resource type."""
        if resource_type and resource_type not in self.preferred_resources:
            self.preferred_resources.append(resource_type)
    
    def is_session_expired(self, timeout_seconds: int = 3600) -> bool:
        """Check if the current session has expired due to inactivity."""
        return self.get_inactive_duration() > timeout_seconds

    def _update_ema(self, current_avg: float, new_value: float, alpha: float = 0.3) -> float: # New helper method
        """Helper to calculate exponential moving average."""
        return (1 - alpha) * current_avg + alpha * new_value

    def update_interaction_pattern(self, response_time: Optional[float] = None, 
                                  message_length: Optional[int] = None) -> None:
        """Update interaction pattern metrics."""
        self.interaction_patterns["total_interactions"] += 1
        
        if response_time is not None:
            # Update average response time with exponential moving average
            self.interaction_patterns["avg_response_time"] = self._update_ema(
                self.interaction_patterns["avg_response_time"], response_time
            )
        
        if message_length is not None:
            # Update average message length with exponential moving average
            self.interaction_patterns["avg_message_length"] = self._update_ema(
                self.interaction_patterns["avg_message_length"], message_length
            )


@dataclass
class AvatarMessage:
    """Message in an Avatar conversation."""
    
    content: str
    role: str  # "user" or "avatar"
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AvatarMessage:
        # Ensure all required fields are present or have defaults
        # field_names = {f.name for f in fields(cls)}
        # filtered_data = {k: v for k, v in data.items() if k in field_names}
        # This simple version assumes data.keys() are a subset of AvatarMessage fields
        # A more robust version would handle missing keys or extra keys gracefully.
        return cls(**data)


class ModelTimeout(Exception):
    """Exception raised when a model call times out."""
    pass


class AvatarService:
    """Service for managing the AI Avatar."""
    
    def __init__(self, 
                max_conversation_history: int = 100,
                model_timeout_seconds: float = 10.0,
                session_timeout_seconds: int = 3600,
                ai_service: Optional[AIService] = None, 
                content_retrieval_service: Optional[ContentRetrievalService] = None,
                content_assembly_service: Optional[ContentAssemblyService] = None,
                content_service: Optional[ContentService] = None): # Added content_service
        """
        Initialize the Avatar service.
        
        Args:
            max_conversation_history: Maximum number of messages to keep per user
            model_timeout_seconds: Timeout for AI model calls in seconds
            session_timeout_seconds: Time before a session is considered expired in seconds
            ai_service: Service for AI-related tasks like lesson/quiz generation.
            content_retrieval_service: Service for fetching external content.
            content_assembly_service: Service for assembling learning pathways.
            content_service: Service for content-related queries (books, videos, etc.).
        """
        self.contexts: Dict[str, AvatarContext] = {}
        self.conversation_history: Dict[str, List[AvatarMessage]] = {}
        self.max_conversation_history = max_conversation_history
        self.model_timeout_seconds = model_timeout_seconds
        self.session_timeout_seconds = session_timeout_seconds
        self._callbacks: Dict[str, List[Callable]] = {
            "new_message": [],
            "sentiment_changed": [],
            "engagement_changed": [],
        }

        # Initialize shared services with actual implementations
        self.logger.info("Initializing shared services for AvatarService...")
        
        # Prepare API keys for ContentRetrievalService from ai_config
        # This assumes ai_config has these attributes or a method to get them.
        # Using getattr for safety, defaulting to None if not found.
        content_api_keys = {
            "youtube": getattr(ai_config, "YOUTUBE_API_KEY", None),
            "google_books": getattr(ai_config, "GOOGLE_BOOKS_API_KEY", None),
            # Add other API keys ContentRetrievalService might need, e.g., "udemy", "coursera"
        }
        # Filter out keys with None values before passing to the service
        filtered_content_api_keys = {k: v for k, v in content_api_keys.items() if v is not None}
        if not filtered_content_api_keys:
            self.logger.warning("No API keys found in ai_config for ContentRetrievalService. Some functionalities might be limited.")
        
        self.content_retrieval_service = ContentRetrievalService(api_keys=filtered_content_api_keys)
        self.content_assembly_service = ContentAssemblyService()

        # Instantiate the placeholder ContentService (as its actual module is not available)
        # This instance is then passed to AIService.
        self.placeholder_content_service = ContentService()
        self.ai_service = AIService(content_service=self.placeholder_content_service)
        self.logger.info("AIService, ContentRetrievalService, ContentAssemblyService initialized.")

        # Initialize agents
        self.agents: Dict[AgentType, LearningAgent] = {
            AgentType.TUTOR: TutorAgent(self),
            AgentType.QUIZ: QuizAgent(self),
            AgentType.CONTENT_CURATOR: ContentCurationAgent(self),
            AgentType.MOTIVATIONAL: MotivationalAgent(self),
        }
        self.orchestrator = AvatarOrchestrator(self, self.agents)
        self.logger.info("Learning agents and orchestrator initialized.")

        self.content_service = content_service # Use the actual ContentService
        self.firestore_db = AvatarFirestore() # Initialize Firestore DB
        self.cache_config = get_cache_config() # Corrected: Ensure this is called correctly
        self.active_contexts: Dict[str, AvatarContext] = {}
        self.context_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def _load_or_create_context(self, user_id: str, session_id: Optional[str]) -> AvatarContext:
        async with self.context_locks[user_id]:
            if user_id in self.active_contexts:
                # Optionally, update session_id if it's new for an existing context
                if session_id and self.active_contexts[user_id].session_id != session_id:
                    self.active_contexts[user_id].session_id = session_id
                return self.active_contexts[user_id]

            # Try to load from cache
            cached_context_data = await get_cached_avatar_context(user_id, self.cache_config)
            if cached_context_data:
                try:
                    context = AvatarContext.from_dict(cached_context_data, self)
                    self.active_contexts[user_id] = context
                    logger.info(f"Loaded context for user {user_id} from cache.")
                    return context
                except Exception as e:
                    logger.warning(f"Failed to load context from cache for user {user_id}: {e}. Re-initializing.")

            # Try to load from Firestore
            try:
                firestore_context_data = await self.firestore_db.get_avatar_context(user_id)
                if firestore_context_data:
                    context = AvatarContext.from_dict(firestore_context_data, self)
                    self.active_contexts[user_id] = context
                    # Cache the loaded context
                    await cache_avatar_context(user_id, context.to_dict(), self.cache_config)
                    logger.info(f"Loaded context for user {user_id} from Firestore and cached.")
                    return context
            except Exception as e:
                logger.warning(f"Failed to load context from Firestore for user {user_id}: {e}. Creating new context.")

            # Create new context if not found or loading failed
            new_context = AvatarContext(user_id=user_id, session_id=session_id, avatar_service=self)
            self.active_contexts[user_id] = new_context
            # Save new context to Firestore and cache
            await self.firestore_db.save_avatar_context(user_id, new_context.to_dict())
            await cache_avatar_context(user_id, new_context.to_dict(), self.cache_config)
            logger.info(f"Created new context for user {user_id} and saved to Firestore/cache.")
            return new_context

    async def _get_context(self, user_id: str, session_id: Optional[str] = None) -> AvatarContext:
        """Internal method to get or create context, ensuring it's loaded."""
        return await self._load_or_create_context(user_id, session_id)

    async def save_context(self, context: AvatarContext) -> None:
        """Saves the context to both cache and Firestore."""
        async with self.context_locks[context.user_id]:
            try:
                context_data = context.to_dict()
                await cache_avatar_context(context.user_id, context_data, self.cache_config)
                await self.firestore_db.save_avatar_context(context.user_id, context_data)
                logger.info(f"Saved context for user {context.user_id} to cache and Firestore.")
            except Exception as e:
                logger.error(f"Error saving context for user {context.user_id}: {e}")
                # Potentially re-raise or handle more gracefully

    async def handle_message(
        self,
        user_id: str,
        message_text: str,
        session_id: Optional[str] = None,
        media_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handles an incoming message from the user."""
        context = await self._get_context(user_id, session_id)
        
        user_message = AvatarMessage(
            content=message_text, 
            role="user", 
            timestamp=time.time(), 
            media_url=media_url
        )
        context.add_message(user_message)

        # Orchestrate the response
        avatar_response_message = await self.orchestrator.route_message(
            user_id=user_id,
            user_message=user_message,
            context=context,
            conversation_history=context.conversation_history # Pass full history
        )
        context.add_message(avatar_response_message)
        
        await self.save_context(context) # Save context after processing

        return avatar_response_message.to_dict() # Return as dict

    async def _generate_response(
        self, 
        prompt: str, 
        user_id: str, 
        context: AvatarContext, # Added context
        max_tokens: int = 150, 
        temperature: float = 0.7,
        persona_override: Optional[AvatarPersona] = None,
        stream: bool = False # Added stream parameter
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Generates a response using the AI service, with streaming support."""
        
        # Construct the full prompt with persona and history
        full_prompt_elements = []
        
        persona_to_use = persona_override or context.persona
        full_prompt_elements.append(f"You are {persona_to_use.value}. {persona_to_use.description}")

        # Add recent conversation history (e.g., last 5 messages)
        recent_history = context.get_recent_history(max_messages=5)
        if recent_history:
            full_prompt_elements.append("Recent conversation:")
            for msg in recent_history:
                full_prompt_elements.append(f"{msg.role.capitalize()}: {msg.content}")
        
        full_prompt_elements.append(f"User: {prompt}")
        full_prompt_elements.append("Avatar:")
        
        final_prompt = "\n".join(full_prompt_elements)

        if stream:
            async def stream_generator():
                try:
                    request = ChatRequest(
                        messages=[{"role": "user", "content": final_prompt}],
                        max_tokens=max_tokens,
                        temperature=temperature,
                        stream=True
                    )
                    async for chunk in self.ai_service.chat(request):
                        if isinstance(chunk, ChatResponseChunk) and chunk.choices:
                            content = chunk.choices[0].delta.content
                            if content:
                                yield content
                except Exception as e:
                    logger.error(f"Error during streaming AI response for user {user_id}: {e}")
                    yield "Sorry, I encountered an issue while generating a response. Please try again."
            return stream_generator()
        else:
            try:
                request = ChatRequest(
                    messages=[{"role": "user", "content": final_prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=False
                )
                response = await self.ai_service.chat(request)
                # Assuming non-streamed response is a single object with choices
                if response and response.choices:
                    return response.choices[0].message.content
                return "I'm not sure how to respond to that."
            except Exception as e:
                logger.error(f"Error generating AI response for user {user_id}: {e}")
                return "Sorry, I had trouble understanding. Could you rephrase?"

    def get_progress_summary(self, user_id: str) -> Dict[str, Any]:
        """Returns a summary of the user's progress and context."""
        if user_id not in self.active_contexts:
            # Attempt to load if not active, though typically it should be by now
            # This path might indicate a need to ensure context is loaded before calling
            # For now, we'll return a default or raise an error
            logger.warning(f"Progress summary requested for user {user_id} with no active context.")
            # Consider loading it: asyncio.run(self._load_or_create_context(user_id, None))
            # Or return empty/default state:
            return {
                "topics_covered": [],
                "learning_goals": [],
                "current_module": None,
                "engagement_level": 0.0,
                "last_interaction": 0.0,
                "error": "Context not loaded or available"
            }

        context = self.active_contexts[user_id]
        return {
            "topics_covered": list(context.topics_covered.keys()),
            "learning_goals": context.learning_goals,
            "current_module": context.current_module,
            "engagement_level": context.engagement_level,
            "last_interaction": context.last_interaction_time,
            "preferred_content_types": context.preferred_content_types,
            "learning_pace": context.learning_pace.value if context.learning_pace else None,
            "sentiment_moving_average": context.sentiment_ema,
            "strengths": context.strengths,
            "areas_for_improvement": context.areas_for_improvement
        }

    async def _detect_intent(
        self, user_id: str, message: str, context: AvatarContext
    ) -> Tuple[AgentType, Optional[str]]:
        """Detects user intent and routes to the appropriate agent."""
        # More sophisticated intent detection can be added here (e.g., using NLU service)
        # For now, simple keyword-based routing
        lower_message = message.lower()

        # Check for quiz-related keywords
        quiz_keywords = ["quiz me", "test me", "give me a quiz", "ask me questions"]
        if any(keyword in lower_message for keyword in quiz_keywords):
            return AgentType.QUIZ, None

        # Check for content curation keywords (more specific examples)
        content_keywords_actions = {
            "find book about": AgentType.CONTENT_CURATION,
            "search for book on": AgentType.CONTENT_CURATION,
            "recommend a book for": AgentType.CONTENT_CURATION,
            "find video about": AgentType.CONTENT_CURATION,
            "show me a video on": AgentType.CONTENT_CURATION,
            "search for course on": AgentType.CONTENT_CURATION,
            "find a course about": AgentType.CONTENT_CURATION,
            "recommend a podcast on": AgentType.CONTENT_CURATION,
        }
        for keyword, agent_type in content_keywords_actions.items():
            if keyword in lower_message:
                # Extract query after keyword
                query = lower_message.split(keyword)[-1].strip()
                # Basic validation: ensure query is not empty
                if query and len(query) > 2: # Avoid empty or too short queries
                    return agent_type, query # Pass the extracted query
                else:
                    # If query is missing or too short, might fall back to Tutor or ask for clarification
                    logger.info(f"Content keyword '{keyword}' detected but query is missing/short for user {user_id}.")
                    break # Stop checking content keywords if one matched but query was bad

        # Check for motivational triggers (e.g., expressions of frustration, low sentiment)
        # This could also be informed by context.sentiment_ema
        if context.get_recent_sentiment() and context.get_recent_sentiment() < -0.2: # Example threshold
            # Check if the user explicitly asks for motivation or help with feeling down
            motivational_phrases = ["i'm feeling down", "i need motivation", "this is hard", "i give up"]
            if any(phrase in lower_message for phrase in motivational_phrases):
                return AgentType.MOTIVATIONAL, None
            # If sentiment is low but no explicit motivational request, Tutor might still handle it
            # or a more subtle motivational nudge could be integrated into Tutor's response.
            # For now, low sentiment without explicit request defaults to Tutor.

        # Default to TutorAgent if no other intent is strongly detected
        return AgentType.TUTOR, None

    async def get_capabilities(self) -> List[str]:
        """Returns a list of capabilities of the avatar system."""
        # This can be expanded based on agents and their specific skills
        capabilities = [
            "Engage in educational conversations.",
            "Provide explanations and answer questions on various topics.",
            "Generate quizzes to test understanding.",
            "Curate and recommend learning content (books, videos, etc.).",
            "Offer motivational support and encouragement.",
            "Adapt to your learning style and pace over time."
        ]
        # Add more specific capabilities from agents if needed
        # For example, if QuizAgent has different quiz types:
        # capabilities.extend(self.quiz_agent.get_supported_quiz_types())
        return capabilities

    async def set_user_preferences(
        self, 
        user_id: str, 
        learning_style: Optional[LearningStyle] = None,
        learning_pace: Optional[LearningPace] = None,
        preferred_content_types: Optional[List[str]] = None,
        # Add other preferences as needed
    ) -> bool:
        """Sets user-specific learning preferences."""
        context = await self._get_context(user_id)
        updated = False
        if learning_style and context.learning_style != learning_style:
            context.set_learning_style(learning_style.value) # Store the string value
            updated = True
        if learning_pace and context.learning_pace != learning_pace:
            context.set_learning_pace(learning_pace.value) # Store the string value
            updated = True
        if preferred_content_types and context.preferred_content_types != preferred_content_types:
            context.preferred_content_types = preferred_content_types
            updated = True
        
        if updated:
            await self.save_context(context)
        return updated

    async def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Retrieves user-specific learning preferences."""
        context = await self._get_context(user_id)
        return {
            "learning_style": context.learning_style,
            "learning_pace": context.learning_pace.value if context.learning_pace else None,
            "preferred_content_types": context.preferred_content_types,
            # Add other preferences
        }

# --- AvatarContext: Manages user-specific state and history ---
class AvatarContext:
    """Manages the context for a user's interaction with the avatar."""
    def __init__(self, user_id: str, avatar_service: AvatarService, session_id: Optional[str] = None):
        self.user_id = user_id
        self.session_id = session_id or str(uuid.uuid4())
        self.avatar_service = avatar_service # Reference to the service for callbacks
        self.persona: AvatarPersona = AvatarPersona.NEUTRAL_EXPERT # Default persona
        self.conversation_history: List[AvatarMessage] = []
        self.topics_covered: Dict[str, datetime] = {} # Topic: last_discussed_time
        self.learning_goals: List[str] = []
        self.current_module: Optional[str] = None
        self.engagement_level: float = 0.5 # Normalized 0-1
        self.last_interaction_time: float = time.time()
        self.sentiment_ema: float = 0.0 # Exponential Moving Average of sentiment
        self.sentiment_alpha: float = 0.2 # Smoothing factor for EMA
        self.learning_style: Optional[str] = None # Store as string from LearningStyle enum
        self.learning_pace: Optional[LearningPace] = LearningPace.MODERATE # Default pace
        self.preferred_content_types: List[str] = ["video", "article"] # Default preferences
        self.strengths: List[str] = []
        self.areas_for_improvement: List[str] = []
        self.preferred_resources: List[str] = [] # e.g., specific websites, channels
        self.quiz_history: List[Dict[str, Any]] = [] # Store quiz attempts and scores
        self.content_interaction_history: List[Dict[str, Any]] = [] # Track interaction with curated content

    def _update_ema(self, current_value: float, new_datapoint: float) -> float:
        """Helper to update an Exponential Moving Average."""
        return (new_datapoint * self.sentiment_alpha) + (current_value * (1 - self.sentiment_alpha))

    def add_message(self, message: AvatarMessage):
        """Adds a message to the conversation history and updates context."""
        self.conversation_history.append(message)
        self.last_interaction_time = message.timestamp
        
        # Update engagement (simple model: more messages = more engagement, decays over time)
        # This could be made more sophisticated
        self.engagement_level = min(1.0, self.engagement_level + 0.05)
        
        # Update sentiment EMA if sentiment is available in message metadata
        if message.metadata and "sentiment" in message.metadata:
            sentiment_score = message.metadata["sentiment"]
            if isinstance(sentiment_score, (float, int)):
                 self.sentiment_ema = self._update_ema(self.sentiment_ema, float(sentiment_score))

    def get_recent_history(self, max_messages: int = 10) -> List[AvatarMessage]:
        """Returns the most recent messages from the history."""
        return self.conversation_history[-max_messages:]

    def add_topic(self, topic: str):
        """Marks a topic as covered or discussed."""
        self.topics_covered[topic] = datetime.now()

    def set_learning_goal(self, goal: str):
        """Sets a learning goal for the user."""
        if goal not in self.learning_goals:
            self.learning_goals.append(goal)

    def set_current_module(self, module_name: str):
        """Sets the current learning module."""
        self.current_module = module_name

    def clear_current_module(self):
        """Clears the current learning module."""
        self.current_module = None

    def switch_persona(self, new_persona: AvatarPersona):
        """Switches the avatar's persona."""
        self.persona = new_persona
        logger.info(f"User {self.user_id} switched persona to {new_persona.value}")

    def set_learning_style(self, style: str): # Takes string value from LearningStyle enum
        """Sets the user's preferred learning style."""
        # Validate if it's a valid LearningStyle string (optional, depends on how strict)
        try:
            LearningStyle(style) # This will raise ValueError if style is not a valid enum member
            self.learning_style = style
        except ValueError:
            logger.warning(f"Invalid learning style '{style}' provided for user {self.user_id}. Not updated.")

    def set_learning_pace(self, pace_str: str): # Takes string value from LearningPace enum
        """Sets the user's preferred learning pace."""
        try:
            pace_enum = LearningPace(pace_str)
            self.learning_pace = pace_enum
        except ValueError:
            logger.warning(f"Invalid learning pace '{pace_str}' for user {self.user_id}. Not updated.")

    def get_recent_sentiment(self) -> Optional[float]:
        """Returns the most recent sentiment score from messages if available, otherwise EMA."""
        # Check last message with sentiment
        for message in reversed(self.conversation_history):
            if message.metadata and "sentiment" in message.metadata:
                sentiment = message.metadata["sentiment"]
                if isinstance(sentiment, (float, int)):
                    return float(sentiment)
        # Fallback to EMA if no recent message has sentiment
        # Only return EMA if it has been updated from its initial value (e.g. not 0.0 if that's the init)
        # This check might need refinement based on how EMA is initialized and updated.
        if self.sentiment_ema != 0.0: # Basic check, assumes 0.0 is the un-updated initial state
             return self.sentiment_ema
    
    def add_strength(self, strength: str):
        if strength not in self.strengths:
            self.strengths.append(strength)

    def add_area_for_improvement(self, area: str):
        if area not in self.areas_for_improvement:
            self.areas_for_improvement.append(area)

    def add_preferred_resource(self, resource_url: str):
        if resource_url not in self.preferred_resources:
            self.preferred_resources.append(resource_url)

    def record_quiz_attempt(self, quiz_id: str, score: float, details: Dict[str, Any]):
        self.quiz_history.append({
            "quiz_id": quiz_id,
            "score": score,
            "timestamp": time.time(),
            "details": details
        })

    def record_content_interaction(self, content_id: str, content_type: str, interaction_type: str, details: Optional[Dict[str, Any]] = None):
        self.content_interaction_history.append({
            "content_id": content_id,
            "content_type": content_type,
            "interaction_type": interaction_type, # e.g., 'viewed', 'completed', 'rated_positive'
            "timestamp": time.time(),
            "details": details or {}
        })

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the context to a dictionary for storage."""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "persona": self.persona.value,
            "conversation_history": [msg.to_dict() for msg in self.conversation_history],
            "topics_covered": {topic: dt.isoformat() for topic, dt in self.topics_covered.items()},
            "learning_goals": self.learning_goals,
            "current_module": self.current_module,
            "engagement_level": self.engagement_level,
            "last_interaction_time": self.last_interaction_time,
            "sentiment_ema": self.sentiment_ema,
            "learning_style": self.learning_style,
            "learning_pace": self.learning_pace.value if self.learning_pace else None,
            "preferred_content_types": self.preferred_content_types,
            "strengths": self.strengths,
            "areas_for_improvement": self.areas_for_improvement,
            "preferred_resources": self.preferred_resources,
            "quiz_history": self.quiz_history,
            "content_interaction_history": self.content_interaction_history,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], avatar_service: AvatarService) -> AvatarContext:
        """Deserializes the context from a dictionary."""
        context = cls(user_id=data["user_id"], avatar_service=avatar_service, session_id=data.get("session_id"))
        context.persona = AvatarPersona(data.get("persona", AvatarPersona.NEUTRAL_EXPERT.value))
        
        # Deserialize conversation history
        context.conversation_history = [
            AvatarMessage.from_dict(msg_data) for msg_data in data.get("conversation_history", [])
        ]
        
        # Deserialize topics_covered (convert ISO strings back to datetime)
        context.topics_covered = {
            topic: datetime.fromisoformat(dt_str) 
            for topic, dt_str in data.get("topics_covered", {}).items()
        }
        
        context.learning_goals = data.get("learning_goals", [])
        context.current_module = data.get("current_module")
        context.engagement_level = data.get("engagement_level", 0.5)
        context.last_interaction_time = data.get("last_interaction_time", time.time())
        context.sentiment_ema = data.get("sentiment_ema", 0.0)
        context.learning_style = data.get("learning_style")
        
        pace_str = data.get("learning_pace")
        if pace_str:
            try:
                context.learning_pace = LearningPace(pace_str)
            except ValueError:
                logger.warning(f"Invalid learning pace '{pace_str}' in stored context for {data['user_id']}. Defaulting.")
                context.learning_pace = LearningPace.MODERATE
        else:
            context.learning_pace = LearningPace.MODERATE # Default if not present
            
        context.preferred_content_types = data.get("preferred_content_types", ["video", "article"])
        context.strengths = data.get("strengths", [])
        context.areas_for_improvement = data.get("areas_for_improvement", [])
        context.preferred_resources = data.get("preferred_resources", [])
        context.quiz_history = data.get("quiz_history", [])
        context.content_interaction_history = data.get("content_interaction_history", [])
        return context

# --- AvatarMessage: Represents a single message in the conversation --- 
@dataclass
class AvatarMessage:
    """Represents a message in the conversation with the avatar."""
    content: str
    role: Literal["user", "avatar", "system"] # system for initial prompts or context setting
    timestamp: float = field(default_factory=time.time)
    media_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict) # For sentiment, intent, etc.

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AvatarMessage:
        # Ensure all required fields are present or have defaults
        # field_names = {f.name for f in fields(cls)}
        # filtered_data = {k: v for k, v in data.items() if k in field_names}
        # This simple version assumes data.keys() are a subset of AvatarMessage fields
        # A more robust version would handle missing keys or extra keys gracefully.
        return cls(**data)

# --- LearningAgent (ABC) and Concrete Agent Implementations ---
class LearningAgent(ABC):
    """Abstract Base Class for all learning agents."""
    def __init__(self, agent_type: AgentType, avatar_service: AvatarService):
        self.agent_type = agent_type
        self.avatar_service = avatar_service

    @abstractmethod
    async def handle_interaction(
        self, 
        user_id: str, 
        message: str, # The user's latest raw message text
        context: AvatarContext,
        # Potentially add conversation_history if needed by specific agents directly
        # For now, context contains history, and _generate_response also uses it.
        query: Optional[str] = None # Specific query extracted by orchestrator/intent detection
    ) -> str: # Returns the text response from the agent
        pass

    async def _generate_response_with_llm(
        self, 
        user_id: str, 
        prompt_message: str, 
        context: AvatarContext,
        max_tokens: int = 200,
        temperature: float = 0.6,
        stream: bool = False # Agents can decide if they want to stream
    ) -> str: # For now, agents return full string; streaming handled by AvatarService if needed by orchestrator
        """Helper for agents to call the LLM via AvatarService."""
        # This method assumes agents will return a single string for now.
        # If agents need to stream, this would need to return an AsyncGenerator.
        # However, the current orchestrator expects a single AvatarMessage back from agent.handle_interaction.
        # So, streaming is better handled at the AvatarService._generate_response level if the final response needs to be streamed.
        
        # Construct a more focused prompt for the agent
        agent_prompt = f"Context: You are the {self.agent_type.value} agent. {context.persona.description}\nUser: {prompt_message}\n{self.agent_type.value} Agent:"
        
        # Use the AvatarService's generator, which handles history and persona already
        # We pass the agent-specific `prompt_message` which might be a rephrasing or specific task for the LLM
        response_content = await self.avatar_service._generate_response(
            prompt=agent_prompt, # Agent-specific framing of the prompt
            user_id=user_id,
            context=context,
            max_tokens=max_tokens,
            temperature=temperature,
            persona_override=context.persona, # Use current context persona unless agent needs to override
            stream=False # Agents currently return full string
        )
        if isinstance(response_content, str):
            return response_content
        else:
            # This case should not happen if stream=False for agents
            # Collect streamed chunks if it somehow returns a generator
            # This is a fallback and ideally _generate_response respects stream=False for agents.
            logger.warning("Agent LLM call unexpectedly returned a stream. Collecting chunks.")
            return "".join([chunk async for chunk in response_content])

class TutorAgent(LearningAgent):
    def __init__(self, avatar_service: AvatarService):
        super().__init__(AgentType.TUTOR, avatar_service)

    async def handle_interaction(self, user_id: str, message: str, context: AvatarContext, query: Optional[str] = None) -> str:
        # Default tutor behavior: explain, answer questions
        # The `message` here is the user's direct input.
        # `query` might be populated if intent detection isolated a specific question/topic.
        
        prompt_for_llm = query if query else message # Use specific query if available
        
        # Add context about current learning goals or module if relevant
        contextual_prompt_elements = [prompt_for_llm]
        if context.current_module:
            contextual_prompt_elements.append(f"(User is currently in module: '{context.current_module}')")
        if context.learning_goals:
            goals_str = ", ".join(context.learning_goals)
            contextual_prompt_elements.append(f"(User's learning goals include: {goals_str})")
        
        final_tutor_prompt = " ".join(contextual_prompt_elements)
        
        return await self._generate_response_with_llm(user_id, final_tutor_prompt, context)

class QuizAgent(LearningAgent):
    def __init__(self, avatar_service: AvatarService):
        super().__init__(AgentType.QUIZ, avatar_service)

    async def handle_interaction(self, user_id: str, message: str, context: AvatarContext, query: Optional[str] = None) -> str:
        # Generate a quiz based on recent topics or a specified topic
        # `query` could be a specific topic for the quiz if provided by intent detection
        
        topic_for_quiz = query # If intent detection provided a topic
        if not topic_for_quiz:
            # If no specific topic, try to pick from recent topics or current module
            if context.current_module:
                topic_for_quiz = context.current_module
            elif context.topics_covered:
                # Pick the most recently discussed topic
                topic_for_quiz = max(context.topics_covered, key=context.topics_covered.get)
            else:
                return "I can give you a quiz, but what topic should it be on?"

        # Placeholder for actual quiz generation logic using ContentAssemblyService
        # This would involve calling a method on self.avatar_service.content_assembly_service
        # For now, simulate with an LLM call to generate a question
        
        # Example: Generate one multiple-choice question
        quiz_prompt = f"Generate a multiple-choice quiz question about '{topic_for_quiz}'. Include 4 options and indicate the correct answer clearly, perhaps by starting the correct option with 'Correct: '."
        
        # Store quiz attempt or details in context if needed
        # context.record_quiz_attempt(...) 
        
        return await self._generate_response_with_llm(user_id, quiz_prompt, context, max_tokens=250)

class ContentCurationAgent(LearningAgent):
    def __init__(self, avatar_service: AvatarService):
        super().__init__(AgentType.CONTENT_CURATOR, avatar_service)

    async def handle_interaction(self, user_id: str, message: str, context: AvatarContext, query: Optional[str] = None) -> str:
        # Curate content based on user request (message or query)
        # `query` will typically be the search term for content (e.g., "python programming")
        
        if not query:
            # If intent detection provided no specific query, ask for clarification.
            return "What kind of content are you looking for? For example, you can ask me to 'find a book about Python'."

        # Determine content type from message if possible, otherwise search broadly or use preferences
        # This is a simplified example. A more robust solution would parse content type.
        content_type_to_search = None
        lower_message = message.lower()
        if "book" in lower_message:
            content_type_to_search = "book"
        elif "video" in lower_message:
            content_type_to_search = "video"
        elif "course" in lower_message:
            content_type_to_search = "course"
        elif "podcast" in lower_message:
            content_type_to_search = "podcast"
        
        # Use the ContentService via AvatarService
        if not self.avatar_service.content_service:
            return "I'm currently unable to search for external content. Please try again later."

        results = None # Initialize results
        try:
            if content_type_to_search == "book":
                results = await self.avatar_service.content_service.search_books(query)
                if results:
                    # context.record_content_interaction(results[0].id, "book", "recommended")
                    return f"I found a book for you: '{results[0].title}' by {results[0].authors[0] if results[0].authors else 'Unknown Author'}. More info: {results[0].info_link}"
            elif content_type_to_search == "video":
                results = await self.avatar_service.content_service.search_videos(query)
                if results:
                    # context.record_content_interaction(results[0].id, "video", "recommended")
                    return f"Here's a video I found: '{results[0].title}' by {results[0].channel}. Watch it here: {results[0].video_url}"
            # Add similar blocks for course, podcast
            else:
                # Generic search or use preferred types if specific type not mentioned
                # For simplicity, let's try searching books first if no type specified
                books = await self.avatar_service.content_service.search_books(query)
                if books:
                    return f"I found a book that might be relevant: '{books[0].title}'. Would you like to know more?"
                videos = await self.avatar_service.content_service.search_videos(query)
                if videos:
                    return f"I found a video that could be helpful: '{videos[0].title}'. Interested?"
                # This return was likely the cause of the "else clause always executed" if it was part of a for/else
                # return f"Sorry, I couldn't find specific content for '{query}' right now. Try rephrasing or specifying a type like 'book' or 'video'."
            
            # This check should be outside the specific type checks if it's a general fallback
            if not results: # If after all checks, results is still None or empty
                # Check if we attempted a search based on content_type_to_search
                if content_type_to_search:
                    return f"Sorry, I couldn't find any {content_type_to_search} about '{query}'."
                else: # This means no specific type was identified and generic searches also failed
                    return f"Sorry, I couldn't find specific content for '{query}' right now. Try rephrasing or specifying a type like 'book' or 'video'."

        except Exception as e:
            logger.error(f"ContentCurationAgent: Error searching for '{query}' (type: {content_type_to_search}): {e}")
            return "I encountered an error while searching for content. Please try again."
        
        # Fallback if no specific content type matched or no results - this might be redundant now
        # return f"I'm having trouble finding specific content about '{query}'. Can you be more specific about the type (e.g., book, video)?"
        # If we reach here, it means some logic path wasn't covered, or a specific return was missed.
        # The conditions above should ideally cover all outcomes.
        # Adding a more generic fallback if somehow missed.
        return f"I looked for content about '{query}' but couldn't find anything specific. You can ask for books, videos, courses, or podcasts."

class MotivationalAgent(LearningAgent):
    def __init__(self, avatar_service: AvatarService):
        super().__init__(AgentType.MOTIVATIONAL, avatar_service)

    async def handle_interaction(self, user_id: str, message: str, context: AvatarContext, query: Optional[str] = None) -> str:
        # Offer encouragement, acknowledge progress, or provide uplifting content
        
        # Check recent sentiment from context
        recent_sentiment = context.get_recent_sentiment()
        
        # Check for explicit motivational request in the message
        is_explicit_request = any(phrase in message.lower() for phrase in ["i need motivation", "feeling down", "encourage me"])

        if is_explicit_request:
            prompt = "The user is explicitly asking for motivation. Offer some encouraging words and perhaps a tip for staying positive."
        elif recent_sentiment is not None and recent_sentiment < -0.3:
            prompt = f"The user seems to be feeling a bit down (sentiment: {recent_sentiment:.2f}). Offer some gentle encouragement. You could also subtly suggest a short break or a fun related activity."
            # Optionally, try to find uplifting content if sentiment is very low
            if recent_sentiment < -0.5 and self.avatar_service.content_service:
                try:
                    podcasts = await self.avatar_service.content_service.search_podcasts("positive thinking short")
                    if podcasts:
                        # Don't make the response too long, just append a suggestion
                        suggestion = f" Perhaps listening to something uplifting like '{podcasts[0].title}' could help?"
                        # The LLM will integrate this naturally if included in its prompt.
                        # For now, we'll let the LLM generate the main message and append this if needed.
                        # This part needs careful crafting to integrate smoothly with LLM response.
                        # For now, let the LLM handle the primary response based on the sentiment prompt.
                except Exception as e:
                    logger.warning(f"MotivationalAgent: Failed to fetch uplifting content: {e}")
        else:
            # Default motivational interaction: acknowledge progress or offer general encouragement
            # This could be triggered periodically or if the user achieves a milestone.
            if context.learning_goals and random.random() < 0.3: # Randomly acknowledge goals
                prompt = f"The user is working towards these goals: {', '.join(context.learning_goals)}. Acknowledge their effort and offer some encouragement related to their goals."
            else:
                prompt = "Offer some general words of encouragement or a fun fact related to learning."
        
        return await self._generate_response_with_llm(user_id, prompt, context, temperature=0.75)

# --- AvatarOrchestrator: Routes messages to appropriate agents ---
class AvatarOrchestrator:
    """Orchestrates interactions between the user and various learning agents."""
    def __init__(self, avatar_service: AvatarService, agents: Dict[AgentType, LearningAgent]):
        self.avatar_service = avatar_service # For access to shared services if needed by orchestrator itself
        self.agents = agents
        self.default_agent = AgentType.TUTOR # Fallback agent

    async def route_message(
        self, 
        user_id: str, 
        user_message: AvatarMessage, 
        context: AvatarContext,
        conversation_history: List[AvatarMessage] # Full history for context
    ) -> AvatarMessage: # Returns the AvatarMessage from the chosen agent
        """Routes the message to an agent and returns the agent's response."""
        
        # 1. Detect intent (which agent should handle this?)
        # The _detect_intent method now also returns an optional query string
        # Pass the full context to intent detection as it might use sentiment, history, etc.
        # Use user_message.content for intent detection
        agent_type, extracted_query = await self.avatar_service._detect_intent(user_id, user_message.content, context)
        
        chosen_agent = self.agents.get(agent_type, self.agents[self.default_agent])
        logger.info(f"Routing message from user {user_id} to {chosen_agent.agent_type.value} agent. Query: '{extracted_query if extracted_query else "N/A"}'")

        # 2. Call the chosen agent's handler
        # Pass the user_message.content as `message` and the `extracted_query` separately.
        try:
            response_text = await chosen_agent.handle_interaction(
                user_id=user_id, 
                message=user_message.content, # Pass the original user message text
                context=context,
                query=extracted_query # Pass the extracted query if any
            )
        except Exception as e:
            logger.error(f"Error during agent ({chosen_agent.agent_type.value}) interaction for user {user_id}: {e}")
            # Fallback response if agent fails
            fallback_agent = self.agents[self.default_agent]
            if chosen_agent.agent_type != self.default_agent:
                logger.info(f"Falling back to {self.default_agent.value} agent for user {user_id}.")
                try:
                    response_text = await fallback_agent.handle_interaction(user_id, user_message.content, context, None)
                except Exception as e_fallback:
                    logger.error(f"Error during fallback agent ({self.default_agent.value}) interaction for user {user_id}: {e_fallback}")
                    response_text = "I seem to be having some trouble processing that. Please try again in a moment."
            else:
                 response_text = "I encountered an issue. Could you please try rephrasing or asking something else?"

        # 3. Construct AvatarMessage from agent's response text
        # Metadata can be added here by the orchestrator or by agents modifying context
        # For now, basic metadata
        response_metadata = {
            "agent_used": chosen_agent.agent_type.value,
            "timestamp": time.time(),
            # Potentially add sentiment of avatar's response if analyzed
        }
        
        # If the agent's response was intended to be streamed, the AvatarService.handle_message
        # would need to handle that. For now, assuming agents return full text.
        return AvatarMessage(content=response_text, role="avatar", metadata=response_metadata)