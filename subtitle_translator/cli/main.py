"""Command-line interface for the subtitle translator."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional, List

from ..core import Translator, TranslationConfig
from ..utils.config import ConfigManager

logger = logging.getLogger(__name__)


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments.
    
    Args:
        args: List of command line arguments. If None, uses sys.argv[1:].
        
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Translate subtitle files using NLLB translation models.'
    )
    
    # Input/output options
    io_group = parser.add_argument_group('Input/Output')
    io_group.add_argument(
        'input',
        type=str,
        help='Input subtitle file or directory'
    )
    io_group.add_argument(
        '-o', '--output',
        type=str,
        help='Output file or directory (default: same as input with language suffix)'
    )
    io_group.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='Process directories recursively'
    )
    io_group.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing files without prompting'
    )
    
    # Language options
    lang_group = parser.add_argument_group('Language')
    lang_group.add_argument(
        '-s', '--source-lang',
        type=str,
        default=None,
        help='Source language code (e.g., eng_Latn)'
    )
    lang_group.add_argument(
        '-t', '--target-lang',
        type=str,
        default=None,
        help='Target language code (e.g., nld_Latn)'
    )
    lang_group.add_argument(
        '--list-languages',
        action='store_true',
        help='List available languages and exit'
    )
    
    # Translation options
    trans_group = parser.add_argument_group('Translation')
    trans_group.add_argument(
        '--translator',
        type=str,
        choices=['local_nllb', 'huggingface'],
        default=None,
        help='Translation backend to use'
    )
    trans_group.add_argument(
        '--endpoint',
        type=str,
        default=None,
        help='Translation endpoint URL (for local_nllb)'
    )
    trans_group.add_argument(
        '--api-key',
        type=str,
        default=None,
        help='API key (for huggingface)'
    )
    trans_group.add_argument(
        '--batch-size',
        type=int,
        default=None,
        help='Number of text segments to translate in a single batch'
    )
    trans_group.add_argument(
        '--timeout',
        type=int,
        default=None,
        help='Request timeout in seconds'
    )
    
    # Output options
    out_group = parser.add_argument_group('Output')
    out_group.add_argument(
        '-v', '--verbose',
        action='count',
        default=0,
        help='Increase verbosity (can be used multiple times)'
    )
    out_group.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress non-error output'
    )
    
    # Config options
    config_group = parser.add_argument_group('Configuration')
    config_group.add_argument(
        '--config',
        type=str,
        help='Path to configuration file'
    )
    config_group.add_argument(
        '--save-config',
        action='store_true',
        help='Save current options to config file'
    )
    
    return parser.parse_args(args)


def setup_logging(verbosity: int = 0, quiet: bool = False) -> None:
    """Configure logging based on verbosity level.
    
    Args:
        verbosity: Verbosity level (0=WARNING, 1=INFO, 2=DEBUG)
        quiet: If True, suppress all non-error output
    """
    if quiet:
        log_level = logging.ERROR
    else:
        log_level = max(
            logging.WARNING - (verbosity * 10),
            logging.DEBUG
        )
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def list_languages(config: ConfigManager) -> None:
    """List available languages and exit.
    
    Args:
        config: Configuration manager
    """
    languages = config.get_available_languages()
    if not languages:
        print("No languages configured.")
        return
    
    max_code_len = max(len(code) for code in languages)
    print(f"{'Code':<{max_code_len}}  Language")
    print('-' * (max_code_len + 2 + 50))  # 50 is a reasonable max for language names
    
    for code, name in sorted(languages.items()):
        print(f"{code:<{max_code_len}}  {name}")


def get_files_to_process(input_path: str, recursive: bool = False) -> List[Path]:
    """Get a list of files to process based on input path.
    
    Args:
        input_path: Input file or directory path
        recursive: Whether to process directories recursively
        
    Returns:
        List of files to process
    """
    path = Path(input_path).expanduser().resolve()
    
    if not path.exists():
        logger.error(f"Path does not exist: {path}")
        return []
    
    if path.is_file():
        return [path]
    
    # Process directory
    files = []
    pattern = '**/*' if recursive else '*'
    
    for ext in ['.srt', '.ass', '.ssa', '.vtt']:
        files.extend(path.glob(f"{pattern}{ext}"))
    
    return sorted(files)


async def process_file(
    input_file: Path,
    output_file: Path,
    config: ConfigManager,
    args: argparse.Namespace
) -> bool:
    """Process a single subtitle file.
    
    Args:
        input_file: Input file path
        output_file: Output file path
        config: Configuration manager
        args: Command line arguments
        
    Returns:
        bool: True if processing was successful, False otherwise
    """
    # Skip if output file exists and not overwriting
    if output_file.exists() and not args.overwrite:
        logger.warning(f"Skipping (file exists, use --overwrite to force): {output_file}")
        return False
    
    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Create translator config
    translator_config = {
        'type': args.translator or config.get('translator.type'),
        'endpoint': args.endpoint or config.get('translator.endpoint'),
        'api_key': args.api_key or config.get('translator.api_key'),
        'batch_size': args.batch_size or config.get('translator.batch_size'),
        'timeout': args.timeout or config.get('translator.timeout'),
    }
    
    # Get languages
    source_lang = args.source_lang or config.get('languages.source')
    target_lang = args.target_lang or config.get('languages.target')
    
    if not source_lang or not target_lang:
        logger.error("Source and target languages must be specified")
        return False
    
    # Initialize translator
    translator = Translator(
        TranslationConfig(
            endpoint=translator_config['endpoint'],
            batch_size=translator_config['batch_size'],
            timeout=translator_config['timeout'],
            source_language=source_lang,
            target_language=target_lang,
        )
    )
    
    try:
        logger.info(f"Translating: {input_file} -> {output_file}")
        logger.info(f"Language: {source_lang} -> {target_lang}")
        
        # Perform translation
        result = await translator.translate_file(
            input_file,
            output_file,
            source_language=source_lang,
            target_language=target_lang
        )
        
        if result.success:
            logger.info(f"Successfully translated: {output_file}")
            return True
        else:
            logger.error(f"Translation failed: {result.error}")
            return False
            
    except Exception as e:
        logger.error(f"Error processing {input_file}: {e}", exc_info=True)
        return False
    finally:
        await translator.close()


def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI.
    
    Args:
        args: Command line arguments. If None, uses sys.argv[1:].
        
    Returns:
        int: Exit code (0 for success, non-zero for error)
    """
    # Parse command line arguments
    args = parse_args(args)
    
    # Set up logging
    setup_logging(verbosity=args.verbose, quiet=args.quiet)
    
    # Initialize config
    config = ConfigManager(args.config)
    
    # List languages and exit if requested
    if args.list_languages:
        list_languages(config)
        return 0
    
    # Validate input
    if not args.input:
        logger.error("Input file or directory is required")
        return 1
    
    # Get files to process
    files = get_files_to_process(args.input, args.recursive)
    if not files:
        logger.error("No valid subtitle files found")
        return 1
    
    # Process each file
    success_count = 0
    
    for input_file in files:
        # Determine output file path
        if args.output:
            output_path = Path(args.output)
            if output_path.is_dir() or str(output_path).endswith('/'):
                output_file = output_path / input_file.name
            else:
                output_file = output_path
        else:
            # Add target language suffix
            lang = args.target_lang or config.get('languages.target', 'translated')
            output_file = input_file.with_name(f"{input_file.stem}_{lang}{input_file.suffix}")
        
        # Process the file
        if asyncio.run(process_file(input_file, output_file, config, args)):
            success_count += 1
    
    # Print summary
    total = len(files)
    logger.info(f"Processed {success_count} of {total} files successfully")
    
    # Save config if requested
    if args.save_config:
        updates = {}
        
        if args.translator:
            updates['translator.type'] = args.translator
        if args.endpoint:
            updates['translator.endpoint'] = args.endpoint
        if args.api_key:
            updates['translator.api_key'] = args.api_key
        if args.batch_size:
            updates['translator.batch_size'] = args.batch_size
        if args.timeout:
            updates['translator.timeout'] = args.timeout
        if args.source_lang:
            updates['languages.source'] = args.source_lang
        if args.target_lang:
            updates['languages.target'] = args.target_lang
        
        if updates:
            config.update(updates)
            logger.info(f"Configuration saved to {config.config_path}")
    
    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
