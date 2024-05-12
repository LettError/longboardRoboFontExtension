"""
    Successor to Skateboard and Superpolator
    Fast, interactive previews of glyphs in a designspace.
    
    erik@letterror.com
    May 2024
"""


from mojo.events import (
    installTool,
    #EditingTool,
    BaseEventTool,
)


class LongboardNavigatorTool(BaseEventTool):
    def setup(self):
        pass

    def getToolbarTip(self):
        return "Longboard Navigator"

nt = LongboardNavigatorTool()
installTool(nt)

