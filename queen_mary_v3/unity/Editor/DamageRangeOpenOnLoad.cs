using UnityEditor;

namespace Naval.EditorTools
{
    // One-shot editor bridge used to bring the damage range scene to the foreground
    // when the project is already open in an editor window.
    [InitializeOnLoad]
    public static class DamageRangeOpenOnLoad
    {
        const string SessionKey = "Naval.DamageRange.OpenedThisSession";

        static DamageRangeOpenOnLoad()
        {
            if (SessionState.GetBool(SessionKey, false)) return;
            SessionState.SetBool(SessionKey, true);
            EditorApplication.delayCall += Open;
        }

        static void Open()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode) return;
            EditorApplication.ExecuteMenuItem("Tools/Naval/Open damage range");
        }
    }
}
