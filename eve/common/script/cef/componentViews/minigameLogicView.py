import cef

class MinigameLogicView(cef.BaseComponentView):
    __guid__ = 'cef.MinigameLogicView'
    __COMPONENT_ID__ = const.cef.MINIGAME_LOGIC_COMPONENT_ID
    __COMPONENT_DISPLAY_NAME__ = 'Minigame Logic'
    __COMPONENT_CODE_NAME__ = 'MinigameLogic'
    GAME_TYPE = 'gameType'

    @classmethod
    def SetupInputs(cls):
        cls.RegisterComponent(cls)
        cls._AddInput(cls.GAME_TYPE, -1, cls.MANDATORY, const.cef.COMPONENTDATA_ID_TYPE)



MinigameLogicView.SetupInputs()
