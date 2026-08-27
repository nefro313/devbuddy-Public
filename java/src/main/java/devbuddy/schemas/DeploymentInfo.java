package devbuddy.schemas;

import java.util.List;

/**
 * Recent deployment history for the service.
 */
public record DeploymentInfo(
        List<DeployRecord> recentDeploys,
        List<String> activeIncidents
) {

    public DeploymentInfo {
        recentDeploys = recentDeploys == null ? List.of() : recentDeploys;
        activeIncidents = activeIncidents == null ? List.of() : activeIncidents;
    }
}
