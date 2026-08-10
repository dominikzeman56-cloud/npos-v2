# neuroman/main.py
import asyncio
from rich.console import Console
from rich.panel import Panel

from .core import NeuroManOrchestrator

console = Console()


async def interactive_loop():
    console.print(
        Panel(
            "[bold cyan]NeuroMan v1.0 (Orchestrator Layer)[/bold cyan]\n"
            "OmniRoute + Producer Pal + Claude Code",
            expand=False,
        )
    )
    orchestrator = NeuroManOrchestrator(console)

    while True:
        try:
            user_input = console.input("\n[bold green]NeuroMan>[/bold green] ")

            if user_input.strip().lower() in ("exit", "quit", "konec"):
                console.print("[yellow]Ukoncuji relaci.[/yellow]")
                break
            if not user_input.strip():
                continue

            await orchestrator.dispatch_task(user_input)

        except KeyboardInterrupt:
            console.print("\n[yellow]Beh preruseny uzivatelem (SIGINT).[/yellow]")
            break
        except Exception as e:
            console.print(f"[bold red]Kriticka chyba v hlavni smycce:[/bold red] {str(e)}")


def main():
    asyncio.run(interactive_loop())


if __name__ == "__main__":
    main()
