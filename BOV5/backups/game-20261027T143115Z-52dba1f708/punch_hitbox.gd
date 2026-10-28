extends Area2D

# The punch hitbox detects overlaps during a short window and calls apply_damage on targets.
# Expected to be instantiated by a fighter and have 'attacker' and 'damage' properties set.

@export var damage: int = 10
var attacker: Node = null

func _ready() -> void:
    # Create a CollisionShape2D if none exists
    if not has_node("CollisionShape2D"):
        var cs = CollisionShape2D.new()
        var shape = RectangleShape2D.new()
        shape.size = Vector2(40, 30)
        cs.shape = shape
        add_child(cs)
    connect("body_entered", Callable(self, "_on_body_entered"))
    # Auto-free shortly to make it a transient hitbox
    await get_tree().create_timer(0.12).timeout
    if is_instance_valid(self):
        queue_free()

func _on_body_entered(body: Node) -> void:
    if not is_instance_valid(attacker):
        return
    # Don't hit the attacker
    if body == attacker:
        return
    if body.has_method("apply_damage"):
        # Compute knockback away from the attacker so the target is pushed correctly
        var dir = 1
        if is_instance_valid(attacker) and attacker.has_method("get_global_position"):
            # Use positions to determine direction: positive to the right
            dir = sign(body.global_position.x - attacker.global_position.x)
            if dir == 0:
                dir = 1
        else:
            # Fallback: assume attacker faces right
            dir = 1
        var knockback = Vector2(200 * dir, -120)
        body.apply_damage(damage, knockback)
        # Only hit once
        queue_free()
