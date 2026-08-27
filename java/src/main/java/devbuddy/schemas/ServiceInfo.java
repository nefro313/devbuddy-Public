package devbuddy.schemas;

/**
 * Identity of the service being evaluated.
 *
 * <p>Equivalent to Python/Node.js {@code ServiceInfo}.</p>
 */
public record ServiceInfo(
        String name,
        String version,
        String ownerTeam
) {

    /** Required-field validation (mirrors Pydantic/Zod required fields). */
    public ServiceInfo {
        if (name == null) {
            throw new IllegalArgumentException("name is required");
        }
        if (version == null) {
            throw new IllegalArgumentException("version is required");
        }
        if (ownerTeam == null) {
            throw new IllegalArgumentException("owner_team is required");
        }
    }
}
