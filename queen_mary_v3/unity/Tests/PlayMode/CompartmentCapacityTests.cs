using NUnit.Framework;
using Naval;
using UnityEngine;

public sealed class CompartmentCapacityTests
{
    [Test]
    public void Flood_IsCappedByCapacity()
    {
        var go = new GameObject("capacity-test");
        try
        {
            var c = go.AddComponent<ShipCompartment>();
            c.floodableVolumeM3 = 100f;
            c.Flood(150f);
            Assert.That(c.FloodedVolumeM3, Is.EqualTo(100f).Within(0.001f));
        }
        finally { Object.DestroyImmediate(go); }
    }
}
