"""Output formatting for CLI."""
from datetime import datetime
from typing import Dict, Any, List, Optional
import json
import csv


class OutputFormatter:
    """Handles formatted output for CLI."""

    @staticmethod
    def print_summary(result: Dict[str, Any], article_num: Optional[int] = None, show_cost: bool = False):
        """
        Print formatted summary to console.

        Args:
            result: Result dictionary from summarizer
            article_num: Article number (for RSS feeds)
            show_cost: Whether to show cost information
        """
        print("\n" + "=" * 80)
        if article_num is not None:
            print(f"📰 DAILY DIGEST - ARTIKEL #{article_num} - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        else:
            print(f"📰 DAILY DIGEST - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 80)
        print(f"\n📌 Titel: {result['title']}")
        print(f"🔗 Quelle: {result['url']}")
        print(f"📑 Typ: {result['source_type'].upper()}")

        # RSS-specific fields
        if 'feed_title' in result:
            print(f"📡 Feed: {result['feed_title']}")
        if 'published' in result and result['published']:
            print(f"📅 Veröffentlicht: {result['published']}")
        if 'author' in result and result['author']:
            print(f"✍️  Autor: {result['author']}")

        if 'language' in result:
            print(f"🌐 Sprache: {result['language']}")

        # Model info
        if 'model_info' in result:
            model_info = result['model_info']
            model_name = model_info.get('name') or model_info.get('model_key') or model_info.get('model')
            print(f"🤖 Modell: {model_name}")

            # Show if fallback was used
            if result.get('fallback_used'):
                print(f"⚠️  Fallback verwendet (Level {result.get('fallback_level', 'unknown')})")

        # Cost info
        if show_cost and 'estimated_cost' in result:
            cost = result['estimated_cost']
            if cost > 0:
                print(f"💰 Geschätzte Kosten: ${cost:.6f}")
            else:
                print("💰 Kosten: Kostenlos")

        print("\n" + "-" * 80)
        print("📝 ZUSAMMENFASSUNG")
        print("-" * 80)
        print(result['summary'])
        print("\n" + "=" * 80 + "\n")

    @staticmethod
    def print_search_results(results: List[Any], query: str, tags: Optional[List[str]] = None, source_type: Optional[str] = None):
        """
        Print search results.

        Args:
            results: List of digest objects
            query: Search query
            tags: Filter tags
            source_type: Filter source type
        """
        print(f"🔍 Searching for: {query}")
        if tags:
            print(f"   Tags: {', '.join(tags)}")
        if source_type:
            print(f"   Type: {source_type}")

        if not results:
            print("\n❌ No results found")
            return

        print(f"\n✅ Found {len(results)} result(s):\n")
        for idx, digest in enumerate(results, 1):
            print(f"{idx}. [{digest.source_type.upper()}] {digest.title}")
            print(f"   URL: {digest.url}")
            print(f"   Created: {digest.created_at.strftime('%Y-%m-%d %H:%M')}")
            if digest.tags:
                tag_names = [dt.tag.name for dt in digest.tags]
                print(f"   Tags: {', '.join(tag_names)}")
            print()

    @staticmethod
    def print_list(results: List[Any], tags: Optional[List[str]] = None, source_type: Optional[str] = None, limit: int = 10):
        """
        Print list of digests.

        Args:
            results: List of digest objects
            tags: Filter tags
            source_type: Filter source type
            limit: Result limit
        """
        print(f"📋 Listing recent digests (limit: {limit})")

        if not results:
            print("\n❌ No digests found")
            return

        print(f"\n✅ {len(results)} digest(s):\n")
        for idx, digest in enumerate(results, 1):
            print(f"{idx}. [{digest.source_type.upper()}] {digest.title}")
            print(f"   URL: {digest.url}")
            print(f"   Created: {digest.created_at.strftime('%Y-%m-%d %H:%M')}")
            print(f"   Provider: {digest.provider}")
            if digest.tags:
                tag_names = [dt.tag.name for dt in digest.tags]
                print(f"   Tags: {', '.join(tag_names)}")
            print()

    @staticmethod
    def print_statistics(stats: Dict[str, Any]):
        """
        Print database statistics.

        Args:
            stats: Statistics dictionary
        """
        print("📊 DATABASE STATISTICS")
        print("=" * 80)
        print(f"\nTotal Digests: {stats['total_digests']}")
        print(f"Total Cost: ${stats['total_cost']:.4f}")
        print(f"Total Tags: {stats['total_tags']}")

        print("\nBy Source Type:")
        for source_type, count in stats['by_source_type'].items():
            print(f"  - {source_type}: {count}")

        print("\n" + "=" * 80)

    @staticmethod
    def print_batch_header(sources_count: int, provider: str, language: str, auto_save: bool, delay: int):
        """
        Print batch processing header.

        Args:
            sources_count: Number of sources
            provider: LLM provider
            language: Summary language
            auto_save: Whether auto-save is enabled
            delay: Delay between sources
        """
        print(f"\n{'='*80}")
        print(f"🚀 BATCH PROCESSING - {sources_count} source(s)")
        print(f"{'='*80}")
        print(f"📋 Provider: {provider}")
        print(f"🌐 Language: {language}")
        print(f"💾 Auto-save: {'Yes' if auto_save else 'No'}")
        print(f"⏱️  Delay between sources: {delay}s")
        print(f"{'='*80}\n")

    @staticmethod
    def print_batch_summary(total_processed: int, total_errors: int, success_rate: float):
        """
        Print batch processing summary.

        Args:
            total_processed: Number of successfully processed items
            total_errors: Number of errors
            success_rate: Success rate percentage
        """
        print(f"\n{'='*80}")
        print("🎉 BATCH PROCESSING COMPLETE")
        print(f"{'='*80}")
        print(f"✅ Total items processed: {total_processed}")
        print(f"❌ Total errors: {total_errors}")
        print(f"📊 Success rate: {success_rate:.1f}%")
        print(f"{'='*80}\n")

    @staticmethod
    def export_to_file(filename: str, data: List[Dict[str, Any]]) -> bool:
        """
        Export data to file (JSON or CSV).

        Args:
            filename: Output filename
            data: List of data dictionaries

        Returns:
            True if successful, False otherwise
        """
        try:
            if not data:
                print("\n❌ No data to export")
                return False

            # Determine format from filename
            if filename.endswith('.json'):
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            elif filename.endswith('.csv'):
                with open(filename, 'w', encoding='utf-8', newline='') as f:
                    if data:
                        fieldnames = list(data[0].keys())
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        for row in data:
                            # Convert lists to strings
                            row_copy = row.copy()
                            if 'tags' in row_copy and isinstance(row_copy['tags'], list):
                                row_copy['tags'] = ', '.join(row_copy['tags'])
                            writer.writerow(row_copy)
            else:
                print("❌ Unsupported format. Use .json or .csv")
                return False

            print(f"✅ Exported {len(data)} digest(s) to {filename}")
            return True

        except Exception as e:
            print(f"❌ Export failed: {e}")
            return False
