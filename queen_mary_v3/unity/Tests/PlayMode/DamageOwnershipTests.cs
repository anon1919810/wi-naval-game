using NUnit.Framework;
using Naval;
using UnityEngine;

public sealed class DamageOwnershipTests
{
    [Test]
    public void PenetratedTarget_DoesNotDamageShooterSystems()
    {
        var shooter = new GameObject("shooter");
        var target = new GameObject("target");
        try
        {
            shooter.AddComponent<ShipIdentity>().instanceId = "player_01";
            target.AddComponent<ShipIdentity>().instanceId = "target_01";
            var own = shooter.AddComponent<ShipSystemsState>();
            var other = target.AddComponent<ShipSystemsState>();
            var part = new GameObject("Boiler_Room_1");
            part.transform.SetParent(target.transform);
            var c = part.AddComponent<ShipCompartment>();
            c.compartmentId = "Boiler_Room_1";
            c.role = "boiler_room";
            c.floodableVolumeM3 = 500f;
            var hit = new ShipPenHit
            {
                outcome = ShipPenOutcome.Penetrated,
                compartmentId = c.compartmentId,
                role = c.role,
                floodM3 = 100f
            };
            Assert.That(ShipDamageApplication.Apply(c, hit), Is.True);
            Assert.That(own.boilerRoomsHit, Is.Zero);
            Assert.That(other.boilerRoomsHit, Is.EqualTo(1));
            Assert.That(c.FloodedVolumeM3, Is.EqualTo(100f).Within(0.001f));
        }
        finally
        {
            Object.DestroyImmediate(shooter);
            Object.DestroyImmediate(target);
        }
    }

    [Test]
    public void Apply_WithoutIdentity_Fails()
    {
        var go = new GameObject("orphan");
        try
        {
            var c = go.AddComponent<ShipCompartment>();
            c.compartmentId = "Boiler_Room_1";
            var hit = new ShipPenHit { outcome = ShipPenOutcome.Penetrated, floodM3 = 10f };
            Assert.That(ShipDamageApplication.Apply(c, hit), Is.False);
        }
        finally { Object.DestroyImmediate(go); }
    }
}

public sealed class ModuleDamageTests
{
    [Test]
    public void RepeatedHit_CountsOneBoilerModule()
    {
        var go = new GameObject("systems");
        try
        {
            var state = go.AddComponent<ShipSystemsState>();
            for (int i = 0; i < 7; i++) state.ApplyModule("Boiler_Room_1", "boiler_room");
            Assert.That(state.boilerRoomsHit, Is.EqualTo(1));
            state.ApplyModule("Boiler_Room_2", "boiler_room");
            Assert.That(state.boilerRoomsHit, Is.EqualTo(2));
            state.ResetSystems();
            Assert.That(state.boilerRoomsHit, Is.Zero);
        }
        finally { Object.DestroyImmediate(go); }
    }
}

public sealed class MovingShipFloodTests
{
    [Test]
    public void Flooding_DoesNotMoveShipRoot()
    {
        var root = new GameObject("ShipRoot");
        try
        {
            root.transform.position = new Vector3(100f, 0f, 200f);
            root.transform.rotation = Quaternion.Euler(0f, 45f, 0f);
            var id = root.AddComponent<ShipIdentity>();
            id.instanceId = "move_01";
            var pose = new GameObject("FloatPose");
            pose.transform.SetParent(root.transform, false);
            var floater = root.AddComponent<ShipFloatPrototype>();
            floater.floatPose = pose.transform;
            var part = new GameObject("Magazine_A");
            part.transform.SetParent(pose.transform, false);
            var c = part.AddComponent<ShipCompartment>();
            c.compartmentId = "Magazine_A";
            c.role = "magazine";
            c.floodableVolumeM3 = 1000f;
            c.belowWaterline = true;
            var hit = new ShipPenHit { outcome = ShipPenOutcome.Penetrated, floodM3 = 200f, role = "magazine" };
            Assert.That(ShipDamageApplication.Apply(c, hit), Is.True);
            Assert.That(root.transform.position.x, Is.EqualTo(100f).Within(0.01f));
            Assert.That(root.transform.position.z, Is.EqualTo(200f).Within(0.01f));
            Assert.That(root.transform.eulerAngles.y, Is.EqualTo(45f).Within(0.2f));
        }
        finally { Object.DestroyImmediate(root); }
    }
}
