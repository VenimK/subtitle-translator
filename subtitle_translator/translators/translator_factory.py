"""Factory for creating translator instances."""

from typing import Dict, Type, Optional, Any

from .base import BaseTranslator
from .local_nllb_translator import LocalNLLBTranslator
from .hf_translator import HFTranslator

class TranslatorFactory:
    """Factory class for creating translator instances."""
    
    # Map of translator types to their corresponding classes
    _translators: Dict[str, Type[BaseTranslator]] = {
        'local_nllb': LocalNLLBTranslator,
        'huggingface': HFTranslator,
    }
    
    @classmethod
    def register_translator(
        cls,
        translator_type: str,
        translator_class: Type[BaseTranslator]
    ) -> None:
        """Register a new translator type.
        
        Args:
            translator_type: Unique identifier for the translator type
            translator_class: Translator class to register
        """
        if not issubclass(translator_class, BaseTranslator):
            raise TypeError(
                f"Translator class must be a subclass of BaseTranslator, "
                f"got {translator_class.__name__}"
            )
        cls._translators[translator_type] = translator_class
    
    @classmethod
    def get_available_translators(cls) -> Dict[str, Type[BaseTranslator]]:
        """Get a dictionary of available translator types and their classes."""
        return dict(cls._translators)
    
    @classmethod
    def create_translator(
        cls,
        translator_type: str,
        config: Optional[Dict[str, Any]] = None
    ) -> BaseTranslator:
        """Create a new translator instance.
        
        Args:
            translator_type: Type of translator to create
            config: Configuration for the translator
            
        Returns:
            An instance of the specified translator type
            
        Raises:
            ValueError: If the specified translator type is not registered
        """
        translator_class = cls._translators.get(translator_type)
        if not translator_class:
            raise ValueError(
                f"Unknown translator type: {translator_type}. "
                f"Available types: {', '.join(cls._translators.keys())}"
            )
        
        return translator_class(config or {})
