using NUnit.Framework;
using Naval;
using UnityEngine;

/// <summary>
/// lod_profiles.json 里 expectedAt 曾长期是「装饰」：它被 JsonUtility 解析成
/// ShipLodExpectedAt 之后，全仓库没有任何一行代码读它。于是「剖面承诺相机在某距离
/// 应看到第几档」这件事既不会被验证，也不会被发现出错 —— 生效阈值其实是
/// 剖面阈值 × QualitySettings.lodBias，两者不一致时 expectedAt 整表都是空谈。
///
/// 这组测试把两件事钉死：
///  ① expectedAt 在自己声明的 recommendedLodBias 下必须成立（否则文档在撒谎）；
///  ② 剖面的 recommendedLodBias 必须等于工程实际生效的 lodBias（否则①再对也没用）。
/// </summary>
public sealed class LodProfileTests
{
    private const string ShipId = "HMS_Queen_Mary_1913";

    private static ShipDefinition LoadDefinition()
    {
        return Resources.Load<ShipDefinition>("Ships/" + ShipId + "/" + ShipId + "_Definition");
    }

    [Test]
    public void Profiles_LoadFromResources()
    {
        var profiles = ShipLodProfiles.Load(ShipId);
        Assert.That(profiles, Is.Not.Null, "lod_profiles.json must be under Assets/Resources/Ships/" + ShipId + "/");
        Assert.That(profiles.profiles, Is.Not.Null);
        Assert.That(profiles.profiles.Length, Is.GreaterThanOrEqualTo(1), "at least one LOD profile is required");
        Assert.That(profiles.Resolve(profiles.default_profile), Is.Not.Null,
            "default_profile " + profiles.default_profile + " must exist");
        foreach (var profile in profiles.profiles)
        {
            Assert.That(profile.id, Is.Not.Null.And.Not.Empty);
            Assert.That(profile.ScreenHeightsOrFallback().Length, Is.EqualTo(4));
        }
    }

    [Test]
    public void ExpectedAt_HoldsUnderRecommendedBias()
    {
        var profiles = ShipLodProfiles.Load(ShipId);
        Assert.That(profiles, Is.Not.Null);
        var definition = LoadDefinition();
        Assert.That(definition, Is.Not.Null, "ShipDefinition asset is required; run ShipRuntimeBuilder first");
        Assert.That(definition.lodGroupSizeMeasured, Is.GreaterThan(0f),
            "lodGroupSizeMeasured must be recorded by ShipLodBuilder (RecalculateBounds 后的 LODGroup.size)");

        foreach (var profile in profiles.profiles)
        {
            if (profile.expectedAt == null) continue;
            var heights = profile.ScreenHeightsOrFallback();
            foreach (var at in profile.expectedAt)
            {
                float rel = ShipLodProfiles.RelativeHeight(
                    definition.lodGroupSizeMeasured, profile.recommendedLodBias, at.distance_m, at.fov_deg);
                int level = ShipLodProfiles.LevelFromRelative(rel, heights);
                Assert.That(level, Is.EqualTo(at.expectedLod),
                    "profile " + profile.id + " @ " + at.distance_m + " m / fov " + at.fov_deg +
                    ": relH=" + rel.ToString("0.000") + " → LOD" + level +
                    ", but expectedAt says LOD" + at.expectedLod +
                    " (recommendedLodBias=" + profile.recommendedLodBias.ToString("0.##") +
                    ", thresholds=[" + string.Join(", ", System.Array.ConvertAll(heights, h => h.ToString("0.00"))) + "])");
            }
        }
    }

    [Test]
    public void RecommendedBias_MatchesProjectQualitySetting()
    {
        var profiles = ShipLodProfiles.Load(ShipId);
        Assert.That(profiles, Is.Not.Null);
        var shipped = profiles.Resolve(profiles.default_profile);
        Assert.That(shipped, Is.Not.Null);

        // 生效阈值 = 剖面阈值 × QualitySettings.lodBias。工程实际值与剖面假设不一致时，
        // expectedAt 无论写什么都不成立 —— 这条断言就是让这种漂移立刻变红。
        Assert.That(shipped.recommendedLodBias, Is.EqualTo(QualitySettings.lodBias).Within(0.001f),
            "shipped profile " + shipped.id + " recommends lodBias " + shipped.recommendedLodBias.ToString("0.##") +
            " but quality level " + QualitySettings.GetQualityLevel() + " uses " + QualitySettings.lodBias.ToString("0.##") +
            "; effective thresholds are multiplied by the latter");

        // 其余剖面也不能为工程永远用不到的 bias 而写，否则同样是空谈。
        foreach (var profile in profiles.profiles)
            Assert.That(profile.recommendedLodBias, Is.EqualTo(shipped.recommendedLodBias).Within(0.001f),
                "profile " + profile.id + " is authored for lodBias " + profile.recommendedLodBias.ToString("0.##") +
                " but the shipped profile uses " + shipped.recommendedLodBias.ToString("0.##"));
    }
}
